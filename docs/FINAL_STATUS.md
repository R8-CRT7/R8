# Final status - 360 SMART 0.5.0-alpha.1 (2026-09-30)

**Legend.** ✅ done · ⏳ prepared, runs automatically once the branch is pushed (GitHub access pending) ·
❌ not done · ➖ not applicable.
*Implemented* = code exists · *Unit tested* = automated tests on the component · *Integration tested* =
automated end-to-end test with real OCR on the simulator · *Manual verified* = I ran it and inspected the
result (screenshots / CLI) · *Device verified* = on real Windows hardware or a real iPhone with the real
360° online software.

**Environment of this work:** Linux container (no Windows, no macOS, no iPhone, no Swift toolchain, no AI
API key). Windows and iOS were therefore verified by tests on Linux + syntax checks, and CI jobs for real
Windows/macOS runners were written but **could not run yet** because pushing to `R8-CRT7/R8` was refused
(HTTP 403 - GitHub App not installed / not connected).

## Windows

| Component | Implemented | Unit tested | Integration tested | Manual verified | Device verified | Notes |
|---|---|---|---|---|---|---|
| State machine + confirmation gate | ✅ | ✅ 33 incl. property-based + races | ✅ | ✅ | ❌ | only `approve_question` enters EXECUTING |
| Composite confidence engine | ✅ | ✅ | ✅ | ✅ | ❌ | "question match" signal reserved (always 1.0) |
| Question cache (safe matching) | ✅ | ✅ | ✅ | ✅ | ❌ | negation bug found + fixed |
| Anthropic provider (structured outputs) | ✅ | ✅ fake SDK client | ✅ via mock | ❌ | ❌ | **no live API call made** (no key) |
| OpenAI / Gemini providers | ✅ | ✅ fake clients | ➖ | ❌ | ❌ | model ids from web research, not live-tested |
| Retry / timeout / circuit breaker / dedup | ✅ | ✅ | ✅ | ✅ | ❌ | |
| Tesseract OCR backend | ✅ | ✅ | ✅ real OCR | ✅ benchmark | ❌ | thread-limit + timeout fix |
| Windows OCR backend (WinRT) | ✅ | ⏳ native CI test | ⏳ | ❌ | ❌ | code written against pywinrt 2.x docs, not executed yet |
| Question/answer extractor + checkbox reader | ✅ | ✅ | ✅ | ✅ calibration screenshots | ❌ | real 360° layout unknown → calibration |
| Change detection + adaptive polling | ✅ | ✅ | ✅ | ✅ profiled 1.7 ms | ❌ | similar-question bug found by soak + fixed |
| Window detection (Win32) | ✅ | ⏳ native CI | ⏳ | ❌ | ❌ | title patterns editable |
| Screen capture (mss) | ✅ | ⏳ native CI | ⏳ real capture E2E | ❌ | ❌ | |
| Input execution (SendInput, atomic, covered-target guard) | ✅ | ⏳ native CI | ⏳ real click E2E | ❌ | ❌ | simulator driver fully tested |
| Verification + max 3 attempts | ✅ | ✅ | ✅ | ✅ | ❌ | |
| Global hotkeys (RegisterHotKey) | ✅ | ⏳ native CI (injected F8) | ➖ | ❌ | ❌ | in-app shortcuts tested |
| Overlay (full / focus / orbit) | ✅ | ✅ pytest-qt | ✅ app round-trip | ✅ screenshots | ❌ | capture exclusion only on Windows |
| Dashboard (9 pages) | ✅ | ✅ | ✅ live engine data | ✅ screenshots | ❌ | |
| Onboarding (5 steps) | ✅ | ✅ | ➖ | ✅ screenshots | ❌ | |
| Calibration wizard | ✅ | ✅ drag → profile | ✅ live test step | ✅ screenshots | ❌ | |
| Startup diagnostics / self-test / export | ✅ | ✅ | ✅ | ✅ CLI + screenshot | ❌ | export has no keys/texts |
| Health monitor, watchdog, UI-lag | ✅ | ✅ | ✅ | ✅ | ❌ | |
| Config (atomic, backup, quarantine) | ✅ | ✅ | ✅ chaos | ✅ | ❌ | |
| Secrets (Credential Manager) | ✅ | ✅ redaction; ⏳ WinVault CI | ➖ | ✅ fallback detection | ❌ | |
| History + Insights | ✅ | ✅ | ✅ | ✅ | ❌ | |
| Sounds (optional) | ✅ | ➖ | ➖ | ⚠ no audio device here | ❌ | fails silently without audio |
| Single-instance lock | ✅ | ✅ | ➖ | ✅ | ❌ | |
| Demo mode (practice simulator) | ✅ | ✅ | ✅ | ✅ app launched (offscreen) | ❌ | free, offline |
| PyInstaller build | ✅ spec | ➖ | ⏳ CI | ❌ | ❌ | not built here (needs Windows) |
| Installer `360SmartSetup.exe` | ✅ .iss | ➖ | ⏳ CI incl. silent install | ❌ | ❌ | unsigned → SmartScreen warning |

## iOS

| Component | Implemented | Unit tested | Integration tested | Manual verified | Device verified | Notes |
|---|---|---|---|---|---|---|
| Smart360Core (models, state machine, cache, confidence, schema, parser) | ✅ | ⏳ 16 XCTests (macOS CI) | ➖ | ✅ Swift syntax check | ❌ | not compiled here |
| AI providers (URLSession) | ✅ | ⏳ body-shape test | ➖ | ❌ | ❌ | no live call |
| SwiftUI app (6 screens, design system, Neural Pulse) | ✅ | ➖ | ⏳ simulator build CI | ❌ | ❌ | |
| Vision OCR | ✅ | ➖ | ⏳ | ❌ | ❌ | |
| Broadcast upload extension | ✅ | ➖ | ⏳ build only | ❌ | ❌ | needs paid account + real device |
| Share extension | ✅ | ➖ | ⏳ build only | ❌ | ❌ | needs paid account |
| App Intent (Shortcuts / Back Tap) | ✅ | ➖ | ⏳ build only | ❌ | ❌ | |
| XcodeGen projects (paid / free) | ✅ | ➖ | ⏳ | ✅ reviewed | ❌ | |
| Live Activities / Dynamic Island | ❌ | ➖ | ➖ | ➖ | ❌ | not built: an extension cannot update a Live Activity; would need an own push server (cost, privacy). Notifications are used instead |
| UI Automation text source (Windows, read DOM text instead of OCR) | ❌ | ➖ | ➖ | ➖ | ❌ | candidate for 0.9 behind a feature flag |

## Measurements (Linux container, 4 vCPU)

| Metric | Value |
|---|---|
| Tests | **145 passed**, 0 failed (7 native-Windows tests deselected on Linux) |
| Lint / types / security | ruff ✅ · mypy ✅ (61 files) · bandit: 0 medium/high · pip-audit: 0 runtime vulns |
| Question extraction (Tesseract, parallel) | median **206 ms** (was 440 ms) |
| OCR accuracy, clean screens (4 scalings) | detected **100 %**, answers exact 90 % |
| OCR accuracy incl. JPEG/blur degradations | detected 93 %, answers exact 78 % (docs/DECISIONS.md D-07) |
| Change detection | 1.7 ms / frame (160×90, mean + changed-pixel rule) |
| Overlay repaint (full) · Neural Pulse | 4.7 ms · 1.4 ms per frame (budget 16.7 ms @ 60 fps) |
| Soak test (30 min, full loop) | see below |

## Soak test
Full loop on the practice simulator for 30 minutes: new question → change detection → real Tesseract OCR →
(mock) AI → approval → click → visual verification → next question. Raw data: `docs/benchmarks/soak_30min.*`.

| | Run 2 (before leak fix) | **Run 3 (final)** |
|---|---|---|
| Full cycles | 1 878 | 1 350 (slower OCR: shared CPU, 311 ms vs 195 ms per call) |
| Correct selections / wrong | 1 690 / 0 | **1 215 / 0** (remainder: number questions, advisory by design) |
| Stuck situations / errors | 0 / 0 | **0 / 0** |
| RSS after warm-up | 81 → 92 MB, linear | **79.6 → 80.8 MB, plateau** (last 12 min: +0.4 MB) |
| RSS trend | +19.5 MB/h | **+3.2 MB/h**, flattening |
| Threads at end | 4 | 4 |

Run 1 was invalid (harness turned pages every 50 ms) and exposed the change-detection bug; run 2 exposed the
pytesseract leak (tracemalloc). Both fixed. A 60-minute run and a run on real Windows are still open.

## What is needed to reach 1.0
1. **GitHub access** → push → Windows CI (native tests, installer) and macOS CI (Swift tests, app build) green.
2. **A real session with 360° online** on Windows: calibrate, check detection on ~50 questions, tune the
   checkbox reader if the real checkboxes differ.
3. **An AI key** for one live run per provider.
4. **iPhone test** (paid Apple account for the extensions).
5. Optional: code-signing certificate for the installer.
