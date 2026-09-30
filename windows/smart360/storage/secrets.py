"""API key storage.

Production: OS credential store via `keyring` (Windows Credential Manager on Windows).
Development: environment variables / a `.env` file are honoured as a fallback.
Keys are never logged; `redact()` scrubs anything key-shaped from log records.
"""

from __future__ import annotations

import logging
import os
import re
from pathlib import Path

log = logging.getLogger(__name__)
SERVICE = "360Smart"

_KEY_PATTERNS = [
    re.compile(r"sk-ant-[A-Za-z0-9_\-]{8,}"),
    re.compile(r"sk-[A-Za-z0-9_\-]{16,}"),
    re.compile(r"AIza[0-9A-Za-z_\-]{20,}"),
    re.compile(r"(?i)(api[_-]?key|authorization|x-api-key)(\"?\s*[:=]\s*\"?)[^\s\",]+"),
]


def redact(text: str) -> str:
    for p in _KEY_PATTERNS[:3]:
        text = p.sub("[REDACTED]", text)
    return _KEY_PATTERNS[3].sub(r"\1\2[REDACTED]", text)


class RedactingFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        try:
            msg = record.getMessage()
        except Exception:
            return True
        red = redact(msg)
        if red != msg:
            record.msg, record.args = red, None
        return True


def _load_dotenv(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    try:
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            out[k.strip()] = v.strip().strip('"').strip("'")
    except OSError:
        pass
    return out


class SecretStore:
    def __init__(self, dotenv: Path | None = None, use_keyring: bool = True):
        self.dotenv = dotenv
        self.use_keyring = use_keyring
        self._memory: dict[str, str] = {}
        self.backend = "memory"
        if use_keyring:
            try:
                import keyring

                kr = keyring.get_keyring()
                name = type(kr).__name__
                if "fail" not in name.lower() and "null" not in name.lower():
                    self.backend = name
                else:
                    self.use_keyring = False
            except Exception:
                self.use_keyring = False

    @property
    def secure(self) -> bool:
        return self.use_keyring

    def get(self, name: str) -> str | None:
        if not name:
            return None
        if self.use_keyring:
            try:
                import keyring

                v = keyring.get_password(SERVICE, name)
                if v:
                    return v
            except Exception as e:
                log.warning("keyring read failed: %s", type(e).__name__)
        if name in self._memory:
            return self._memory[name]
        env = os.environ.get(name)
        if env:
            return env
        if self.dotenv and self.dotenv.exists():
            return _load_dotenv(self.dotenv).get(name)
        return None

    def set(self, name: str, value: str) -> bool:
        """Returns True if stored in the secure OS store, False if memory-only."""
        value = value.strip()
        if self.use_keyring:
            try:
                import keyring

                keyring.set_password(SERVICE, name, value)
                return True
            except Exception as e:
                log.warning("keyring write failed: %s", type(e).__name__)
        self._memory[name] = value
        return False

    def delete(self, name: str) -> None:
        self._memory.pop(name, None)
        if self.use_keyring:
            try:
                import keyring

                keyring.delete_password(SERVICE, name)
            except Exception:
                pass

    @staticmethod
    def mask(value: str | None) -> str:
        if not value:
            return "not set"
        return f"{value[:6]}…{value[-4:]}" if len(value) > 14 else "••••"
