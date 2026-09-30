# Decision log

Each entry: **Problem · Options · Decision · Why · Trade-offs**.

---

## D-01 Windows technology: Python + PySide6

**Problem.** The Windows app needs a premium custom UI, a transparent always-on-top overlay, screen
capture, OCR, Win32 input, global hotkeys, and has to be built and tested largely without a
Windows machine (development ran in a Linux container; Windows is verified in CI).

**Options.** PySide6 · Tauri (Rust + web UI) · WinUI 3 (C#) · Avalonia (C#) · Electron · WPF · Flutter Desktop.

| | PySide6 | Tauri | WinUI 3 | Avalonia | Electron | WPF | Flutter |
|---|---|---|---|---|---|---|---|
| Custom-painted premium UI | ✅ QPainter, 60 fps | ✅ CSS | ✅ | ✅ | ✅ | ✅ | ✅ |
| Transparent overlay / capture exclusion | ✅ | ⚠ webview quirks | ✅ | ✅ | ⚠ | ✅ | ⚠ |
| OCR / CV / AI SDK ecosystem | ✅ best (Pillow, numpy, official AI SDKs) | ⚠ sidecar needed | ⚠ | ⚠ | ⚠ | ⚠ | ⚠ |
| Win32 / UIA integration | ✅ ctypes | ✅ Rust | ✅ | ⚠ | ⚠ | ✅ | ⚠ |
| Develop + test headless on Linux | ✅ offscreen Qt | ⚠ | ❌ | ✅ | ✅ | ❌ | ⚠ |
| Memory | ~130 MB | ~80 MB | ~90 MB | ~120 MB | 250+ MB | ~100 MB | ~150 MB |
| Packaging | PyInstaller + Inno | MSI native | MSIX | ✅ | ✅ | ✅ | ✅ |

**Decision.** Python 3.12 + PySide6 with fully custom-painted widgets (no stock QWidget look).

**Why.** One language for capture, CV, OCR, AI and UI; the whole pipeline is unit/integration
tested on Linux (offscreen Qt, real Tesseract OCR) and natively on Windows in CI.

**Trade-offs.** Larger installer (~120 MB) than Tauri/WinUI; the Python runtime ships inside the
app (the user does **not** install Python).

## D-02 Confirmation gate lives in the state machine, enforced by a token

**Problem.** "No unattended answers" must be technically impossible to bypass, including by bugs.

**Decision.** `EXECUTING_CONFIRMED_ACTION` is absent from the transition table *and* rejected by
the generic `transition()`. Only `approve_question(question_id)` enters it, and only from
`WAITING_FOR_CONFIRMATION`, for the current question id and generation. It mints a single-use
`ApprovalToken` the executor must present; every new capture/pause/error bumps the generation
and invalidates tokens. Tested statically, explicitly, with 16-thread races and a 400-case
property-based random walk.

**Trade-offs.** Slightly more ceremony in the executor (it re-validates the token before every click).

## D-03 Execution re-verifies the screen and maps answers by text

**Problem.** Coordinates from the analysis may be stale (window moved, question changed, answers shuffled).

**Decision.** After approval the executor captures again, requires the visible question to be the
approved one (fuzzy identity: numbers, words, answer set, image), locates the approved answers by
**text** in the fresh capture, reads the current checkbox states, clicks only the difference,
re-checks the window position before each click and visually verifies the result. Max 3 attempts.

## D-04 Cache safety: many signals, exact numbers, no word insertions

**Problem.** A cache must never answer a different question. Plain fuzzy matching fails:
"…dürfen Sie **nicht** überholen?" is 98.5 % similar to the positive question (measured).

**Decision.** A hit requires the same question type, identical number tokens (question and each
answer), ≥ 97 % text similarity **and** no whole-word insertions/deletions, a 1:1 answer
mapping (≥ 95 %) and image agreement (dHash distance ≤ 6). Stored answers are texts, re-mapped to
the current order.

## D-05 Composite confidence = weighted geometric mean + caps

A single weak signal (bad OCR) must pull confidence down more than an average would. Floors cap
the result (OCR < 55 % → max 60 %), `uncertain=true` caps below the manual-check threshold.

## D-06 OCR: Windows.Media.Ocr first, Tesseract fallback, AI vision always gets the image

Windows OCR ships with Windows (offline, no install, fast). Tesseract is the cross-platform
fallback and the engine used in Linux CI. PaddleOCR/EasyOCR were rejected: 200 MB–1 GB of
PyTorch/Paddle dependencies for a UI with clean rendered text. The AI always receives the
situation image; text crops are only sent when OCR confidence is low (cost saver).

## D-06b Tesseract is called directly, not through pytesseract

The 30-minute soak test showed linear RSS growth (+19.5 MB/h). tracemalloc traced it to pytesseract's
cleanup (`glob(f"{unique_tmp_name}*")` per call → `fnmatch` caches every compiled pattern, LRU up to
32 768 entries). A 40-line runner (fixed argv, per-call temp dir, TSV parsing, hard timeout) removes the
leak and a dependency.

## D-07 No image sharpening before OCR (A/B-tested)

Measured on 120 simulator screens × 4 scalings × 3 degradations (Tesseract):

| Variant | detected | answers exact | median |
|---|---|---|---|
| baseline | 0.93 | 0.74 | 444 ms |
| parser fixes, no sharpening | 0.93 | **0.78** | **465 ms** |
| parser fixes + mild unsharp mask | **0.95** | 0.76 | 507 ms |

Sharpening helps blurred input but amplifies JPEG artefacts; real screen captures are lossless,
where all variants detect 100 %. Chosen: no sharpening (more exact, faster).

## D-08 Global ENTER/ESC only while a question awaits confirmation

Registering ENTER globally would swallow Enter in every app. The hotkeys are registered only in
`WAITING_FOR_CONFIRMATION`, and ENTER is **not** registered at all for manual-check predictions
(the user has to click CONFIRM ANYWAY).

## D-09 Packaging: PyInstaller onedir + Inno Setup

Nuitka produces faster/smaller binaries and fewer AV false positives but PySide6 builds take
20–40 min and are brittle on CI; PyInstaller onedir (no self-extraction, no UPX) avoids most
false positives and builds in ~3 min. Inno Setup produces a per-user `360SmartSetup.exe` (no admin).
Code signing (the real fix for SmartScreen) needs a paid certificate - documented, not bought.

## D-10 iOS: honest capture workflows, no control of other apps

iOS forbids controlling other apps. 360 SMART therefore offers (1) screenshot import, (2) a
ReplayKit broadcast upload extension that analyses the live screen and delivers results as
notifications, (3) a Share extension and (4) an App Intent for Shortcuts / Back Tap. "Confirm"
records the user's decision. The phone layout is not calibrated, so the model extracts question
and answers from the screenshot (structured output) and on-device Vision OCR feeds the cache.

## D-11 iOS networking via URLSession (no third-party SDK)

There is no official Anthropic Swift SDK; the Messages API is called over HTTPS with structured
outputs (`output_config.format`). Same for OpenAI/Gemini. Zero third-party Swift dependencies.

## D-12b Change detection: mean difference OR changed-pixel fraction

**Problem.** The soak test stalled: consecutive text-only questions with similar layout differ by a mean of
0.96 grey levels at 64×36 - below any sane threshold. **Decision.** 160×90 signature; change if mean ≥ 3.0
**or** ≥ 1 % of pixels changed by > 24 levels; stable for 2 frames. **Trade-off.** More sensitive to
hover effects - harmless, because a re-captured identical question keeps its prediction (OCR only, no AI call).

## D-12 Default model

Anthropic `claude-opus-5-5` with `effort: low` (fast enough for theory questions) and the
server-side refusal fallback (`fallbacks: "default"`). Users can pick Sonnet 5.5 / Haiku 4.5
(cheaper) or OpenAI/Gemini in settings.
