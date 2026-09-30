"""Win32 integration via ctypes (no pywin32 dependency).

Everything is guarded by `IS_WINDOWS`; on other platforms the functions are inert so
the rest of the app (and the test suite) runs anywhere.

Covers: per-monitor DPI awareness, window enumeration/detection, client-rect lookup,
mouse input via SendInput, overlay capture exclusion and global hotkeys.
"""

from __future__ import annotations

import ctypes
import logging
import re
import sys
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass

from smart360.core.models import Rect

log = logging.getLogger(__name__)
IS_WINDOWS = sys.platform == "win32"

if IS_WINDOWS:
    from ctypes import wintypes

    user32 = ctypes.WinDLL("user32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    shcore = None
    try:
        shcore = ctypes.WinDLL("shcore")
    except OSError:
        pass


# --------------------------------------------------------------------------- DPI


def enable_dpi_awareness() -> str:
    """Per-monitor v2 awareness so capture pixels == input coordinates on scaled displays."""
    if not IS_WINDOWS:
        return "n/a"
    try:
        # DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2 = -4
        if user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4)):
            return "per-monitor-v2"
    except (AttributeError, OSError):
        pass
    try:
        if shcore is not None and shcore.SetProcessDpiAwareness(2) == 0:
            return "per-monitor"
    except OSError:
        pass
    try:
        user32.SetProcessDPIAware()
        return "system"
    except OSError:
        return "unaware"


# --------------------------------------------------------------------------- windows


@dataclass(frozen=True, slots=True)
class WindowInfo:
    hwnd: int
    title: str
    class_name: str
    process: str
    client: Rect
    minimized: bool
    foreground: bool


DEFAULT_TITLE_PATTERNS = (
    r"360\s*°?\s*online",
    r"click\s*&\s*learn",
    r"degener",
    r"360°",
    r"fahrschul-?campus",
)
BROWSER_PROCESSES = ("chrome.exe", "msedge.exe", "firefox.exe", "brave.exe", "opera.exe", "vivaldi.exe")


def _process_name(hwnd: int) -> str:
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    h = kernel32.OpenProcess(0x1000, False, pid.value)  # PROCESS_QUERY_LIMITED_INFORMATION
    if not h:
        return ""
    try:
        buf = ctypes.create_unicode_buffer(520)
        size = wintypes.DWORD(520)
        if kernel32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size)):
            return buf.value.rsplit("\\", 1)[-1].lower()
        return ""
    finally:
        kernel32.CloseHandle(h)


def client_rect(hwnd: int) -> Rect | None:
    if not IS_WINDOWS:
        return None
    r = wintypes.RECT()
    if not user32.GetClientRect(hwnd, ctypes.byref(r)):
        return None
    pt = wintypes.POINT(0, 0)
    if not user32.ClientToScreen(hwnd, ctypes.byref(pt)):
        return None
    rect = Rect(pt.x, pt.y, r.right - r.left, r.bottom - r.top)
    return rect if rect.is_valid() else None


def is_window(hwnd: int) -> bool:
    return bool(IS_WINDOWS and user32.IsWindow(hwnd))


def list_windows() -> list[WindowInfo]:
    if not IS_WINDOWS:
        return []
    out: list[WindowInfo] = []
    fg = user32.GetForegroundWindow()
    enum_proc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def cb(hwnd, _lparam):  # type: ignore[no-untyped-def]
        if not user32.IsWindowVisible(hwnd):
            return True
        n = user32.GetWindowTextLengthW(hwnd)
        if n == 0:
            return True
        title = ctypes.create_unicode_buffer(n + 1)
        user32.GetWindowTextW(hwnd, title, n + 1)
        cls = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(hwnd, cls, 256)
        rect = client_rect(hwnd) or Rect(0, 0, 0, 0)
        out.append(
            WindowInfo(
                int(hwnd),
                title.value,
                cls.value,
                _process_name(hwnd),
                rect,
                bool(user32.IsIconic(hwnd)),
                hwnd == fg,
            )
        )
        return True

    user32.EnumWindows(enum_proc(cb), 0)
    return out


def score_window(w: WindowInfo, patterns: tuple[str, ...] = DEFAULT_TITLE_PATTERNS) -> float:
    """Heuristic match score for the 360° learning window (0 = no match)."""
    title = w.title.lower()
    score = 0.0
    for i, p in enumerate(patterns):
        if re.search(p, title, re.IGNORECASE):
            score = max(score, 1.0 - i * 0.05)
    if score == 0:
        return 0.0
    if w.process in BROWSER_PROCESSES:
        score += 0.1
    if w.client.area > 400 * 300:
        score += 0.1
    if w.minimized:
        score -= 0.5
    if w.foreground:
        score += 0.05
    return score


def find_learning_window(patterns: tuple[str, ...] = DEFAULT_TITLE_PATTERNS) -> WindowInfo | None:
    best, best_score = None, 0.0
    for w in list_windows():
        s = score_window(w, patterns)
        if s > best_score:
            best, best_score = w, s
    return best


def window_info(hwnd: int) -> WindowInfo | None:
    for w in list_windows():
        if w.hwnd == hwnd:
            return w
    return None


def foreground_hwnd() -> int:
    return int(user32.GetForegroundWindow()) if IS_WINDOWS else 0


def bring_to_front(hwnd: int) -> bool:
    if not IS_WINDOWS:
        return False
    return bool(user32.SetForegroundWindow(hwnd))


# --------------------------------------------------------------------------- input

if IS_WINDOWS:
    ULONG_PTR = ctypes.c_size_t

    class MOUSEINPUT(ctypes.Structure):
        _fields_ = [
            ("dx", wintypes.LONG),
            ("dy", wintypes.LONG),
            ("mouseData", wintypes.DWORD),
            ("dwFlags", wintypes.DWORD),
            ("time", wintypes.DWORD),
            ("dwExtraInfo", ULONG_PTR),
        ]

    class KEYBDINPUT(ctypes.Structure):
        _fields_ = [
            ("wVk", wintypes.WORD),
            ("wScan", wintypes.WORD),
            ("dwFlags", wintypes.DWORD),
            ("time", wintypes.DWORD),
            ("dwExtraInfo", ULONG_PTR),
        ]

    class _INPUTUNION(ctypes.Union):
        _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT)]

    class INPUT(ctypes.Structure):
        _fields_ = [("type", wintypes.DWORD), ("u", _INPUTUNION)]


MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
KEYEVENTF_UNICODE = 0x0004
KEYEVENTF_KEYUP = 0x0002


def cursor_pos() -> tuple[int, int]:
    if not IS_WINDOWS:
        return (0, 0)
    pt = wintypes.POINT()
    user32.GetCursorPos(ctypes.byref(pt))
    return (pt.x, pt.y)


def click(x: int, y: int, restore_cursor: bool = True) -> None:
    """Left click at absolute screen pixel (x, y) (process must be DPI aware)."""
    if not IS_WINDOWS:
        raise RuntimeError("input injection is only available on Windows")
    old = cursor_pos()
    if not user32.SetCursorPos(int(x), int(y)):
        raise OSError(ctypes.get_last_error(), "SetCursorPos failed")
    time.sleep(0.02)
    inputs = (INPUT * 2)()
    inputs[0].type = 0
    inputs[0].u.mi = MOUSEINPUT(0, 0, 0, MOUSEEVENTF_LEFTDOWN, 0, 0)
    inputs[1].type = 0
    inputs[1].u.mi = MOUSEINPUT(0, 0, 0, MOUSEEVENTF_LEFTUP, 0, 0)
    sent = user32.SendInput(2, inputs, ctypes.sizeof(INPUT))
    if sent != 2:
        raise OSError(ctypes.get_last_error(), "SendInput blocked (UIPI / secure desktop?)")
    if restore_cursor:
        time.sleep(0.03)
        user32.SetCursorPos(*old)


def type_text(text: str) -> None:
    if not IS_WINDOWS:
        raise RuntimeError("input injection is only available on Windows")
    arr = (INPUT * (len(text) * 2))()
    for i, ch in enumerate(text):
        for j, flags in enumerate((KEYEVENTF_UNICODE, KEYEVENTF_UNICODE | KEYEVENTF_KEYUP)):
            arr[i * 2 + j].type = 1
            arr[i * 2 + j].u.ki = KEYBDINPUT(0, ord(ch), flags, 0, 0)
    user32.SendInput(len(arr), arr, ctypes.sizeof(INPUT))


# --------------------------------------------------------------------------- overlay helpers

WDA_EXCLUDEFROMCAPTURE = 0x11


def exclude_from_capture(hwnd: int) -> bool:
    """Our overlay must never appear in our own screenshots (Windows 10 2004+)."""
    if not IS_WINDOWS:
        return False
    try:
        return bool(user32.SetWindowDisplayAffinity(wintypes.HWND(hwnd), WDA_EXCLUDEFROMCAPTURE))
    except OSError:
        return False


def enable_backdrop(hwnd: int, kind: int = 3) -> bool:
    """Windows 11 system backdrop (2 = Mica, 3 = Acrylic, 4 = Tabbed). Best effort."""
    if not IS_WINDOWS:
        return False
    try:
        dwm = ctypes.WinDLL("dwmapi")
        dark = ctypes.c_int(1)
        dwm.DwmSetWindowAttribute(wintypes.HWND(hwnd), 20, ctypes.byref(dark), 4)  # immersive dark mode
        val = ctypes.c_int(kind)
        return dwm.DwmSetWindowAttribute(wintypes.HWND(hwnd), 38, ctypes.byref(val), 4) == 0
    except OSError:
        return False


# --------------------------------------------------------------------------- hotkeys

MOD_ALT, MOD_CONTROL, MOD_SHIFT, MOD_NOREPEAT = 0x1, 0x2, 0x4, 0x4000
VK = {"ENTER": 0x0D, "ESC": 0x1B, "F8": 0x77, "F9": 0x78, "M": 0x4D, "Q": 0x51, "P": 0x50}


def parse_hotkey(spec: str) -> tuple[int, int]:
    parts = [p.strip().upper() for p in spec.split("+") if p.strip()]
    mods, key = MOD_NOREPEAT, None
    for p in parts:
        if p in ("CTRL", "CONTROL"):
            mods |= MOD_CONTROL
        elif p == "SHIFT":
            mods |= MOD_SHIFT
        elif p == "ALT":
            mods |= MOD_ALT
        elif p in VK:
            key = VK[p]
        elif len(p) == 1 and p.isalnum():
            key = ord(p)
        else:
            raise ValueError(f"unsupported key {p!r} in {spec!r}")
    if key is None:
        raise ValueError(f"no key in {spec!r}")
    return mods, key


class GlobalHotkeys:
    """RegisterHotKey on a dedicated thread with its own message loop.

    Hotkeys can be enabled/disabled dynamically (ENTER/ESC are only registered while a
    question awaits confirmation, so they do not swallow Enter in other apps the rest
    of the time)."""

    WM_HOTKEY = 0x0312
    WM_APP_SYNC = 0x8001

    def __init__(self, on_hotkey: Callable[[str], None]):
        self.on_hotkey = on_hotkey
        self._wanted: dict[str, str] = {}  # action -> spec
        self._active: dict[int, str] = {}
        self._failed: set[str] = set()
        self._thread: threading.Thread | None = None
        self._thread_id = 0
        self._lock = threading.Lock()
        self._ready = threading.Event()

    @property
    def failed(self) -> set[str]:
        return set(self._failed)

    def start(self) -> bool:
        if not IS_WINDOWS:
            return False
        self._thread = threading.Thread(target=self._run, name="hotkeys", daemon=True)
        self._thread.start()
        self._ready.wait(2)
        return True

    def set_bindings(self, bindings: dict[str, str]) -> None:
        with self._lock:
            self._wanted = dict(bindings)
        if IS_WINDOWS and self._thread_id:
            user32.PostThreadMessageW(self._thread_id, self.WM_APP_SYNC, 0, 0)

    def stop(self) -> None:
        if IS_WINDOWS and self._thread_id:
            user32.PostThreadMessageW(self._thread_id, 0x0012, 0, 0)  # WM_QUIT

    def _sync(self) -> None:
        for hk_id in list(self._active):
            user32.UnregisterHotKey(None, hk_id)
        self._active.clear()
        self._failed.clear()
        with self._lock:
            wanted = dict(self._wanted)
        for i, (action, spec) in enumerate(sorted(wanted.items()), start=1):
            try:
                mods, vk = parse_hotkey(spec)
            except ValueError:
                self._failed.add(action)
                continue
            if user32.RegisterHotKey(None, i, mods, vk):
                self._active[i] = action
            else:
                self._failed.add(action)  # taken by another app

    def _run(self) -> None:
        self._thread_id = kernel32.GetCurrentThreadId()
        msg = wintypes.MSG()
        user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, 0)  # create the queue
        self._sync()
        self._ready.set()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            if msg.message == self.WM_HOTKEY:
                action = self._active.get(int(msg.wParam))
                if action:
                    try:
                        self.on_hotkey(action)
                    except Exception:
                        log.exception("hotkey handler failed")
            elif msg.message == self.WM_APP_SYNC:
                self._sync()
        for hk_id in list(self._active):
            user32.UnregisterHotKey(None, hk_id)
