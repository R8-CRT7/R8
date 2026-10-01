# Final status - 360 SMART 0.5.0-alpha.3 (2026-10-01)

## Verification overview (read this first)

| Area | CI tested | Simulator tested | Real Windows PC | Real 360° online software | Real API call | iPhone |
|---|---|---|---|---|---|---|
| Confirmation gate, state machine, cache, confidence | ✅ Linux + Windows runner | ✅ | ❌ | ❌ | ➖ | ➖ |
| Window detection, capture, Windows OCR, SendInput | ✅ Windows runner (real desktop session) | ✅ | ❌ | ❌ | ➖ | ➖ |
| Safe mode (no click when unsure / ambiguous / moved / covered) | ✅ | ✅ | ❌ | ❌ | ➖ | ➖ |
| Dry run (shows where it would click, clicks nothing) | ✅ incl. native | ✅ | ❌ | ❌ | ➖ | ➖ |
| Emergency stop (Ctrl+Shift+X / STOP) | ✅ engine + app | ✅ | ❌ | ❌ | ➖ | ➖ |
| Session trace, test protocol, metrics | ✅ | ✅ | ❌ | ❌ | ➖ | ➖ |
| "Create diagnosis" ZIP (no keys/passwords/tokens) | ✅ Linux + Windows runner + installed app | ✅ | ❌ | ❌ | ➖ | ➖ |
| Installer `360SmartSetup.exe` (install, start, self-test, uninstall) | ✅ silent, on the runner | ➖ | ❌ | ➖ | ➖ | ➖ |
| AI providers (Anthropic / OpenAI / Gemini) | ✅ with fake SDK clients | ✅ with the offline demo AI | ❌ | ❌ | ❌ **no live call ever made** | ➖ |
| iOS app + extensions | ✅ macOS runner: Swift tests, simulator + device builds (unsigned), analyze | ➖ | ➖ | ❌ | ❌ | ❌ never installed |

**In plain words:**
* Everything above was verified **only by automated tests**: in a Linux container, on GitHub-hosted
  Windows/macOS runners (virtual machines), and against the built-in **practice simulator**.
* **Nothing** has run yet on your PC, against the **real 360° online software**, with a **real AI key**, or
  on an **iPhone**.
* That is exactly what [`REAL_DEVICE_TEST.md`](../REAL_DEVICE_TEST.md) is for. Every ❌ above stays ❌ until a
  diagnosis ZIP from a real session shows it working.

Legend: ✅ verified as the column says · ❌ not done · ➖ not applicable.

## Phase "real-PC readiness" (alpha.3) - what changed and why

| # | Change | Why | Tests |
|---|---|---|---|
| 1 | **Never click without a readable checkbox state** | Bug reproduced: with unreadable states the executor clicked anyway, verification failed and the 3 attempts toggled the boxes back (6 clicks for 2 answers) | `test_unreadable_checkbox_state_never_clicks` (red before the fix) |
| 2 | **Ambiguous target → no click** | Bug reproduced: an approved text matching two answers picked the first one (3 wrong attempts) | `test_ambiguous_target_never_clicks` (red before the fix) |
| 3 | **Real checkbox detection** (square outline, also inside the OCR line); estimates flagged | All simulator checkboxes were only *estimated* before (the estimate happened to be right) | 144/144 found on the simulator (4 scalings × clean/JPEG/blur), 0 wrong; false-positive tests with text only; native: found on real Windows rendering |
| 4 | **Safe mode** (default on) | First real tests: no click for low confidence, estimated checkboxes, a window moved since the question was read, ambiguous targets; no click retries | 13 tests in `test_safety.py` |
| 5 | **Dry run** (default on) | See exactly where it would click (overlay message, on-screen crosses, trace picture), click nothing | engine, app, native (no input reached the window) |
| 6 | **Emergency stop** Ctrl+Shift+X (always global), STOP button, tray | Pause could not interrupt a running execution (same command queue). The stop voids the approval under the state-machine lock and is checked immediately before every SendInput | waiting / during execution (2nd click dropped) / during analysis / app shows STOPPED |
| 7 | **Session trace + protocol + metrics** | Per question: capture → OCR → answers → AI → confidence → decision → execution capture → verification → click / no click + reason | `test_diagnostics.py` |
| 8 | **Create diagnosis (ZIP)**: button, tray, `--diagnose`, Start-menu shortcut | You should not have to debug. Contains versions/build, Windows, monitors, DPI, window, OCR, confidence, coordinates, state changes, logs, traces | secrets planted in config/logs/trace are absent from the ZIP (pattern + verbatim scrub) |
| 9 | `REAL_DEVICE_TEST.md` | Step-by-step guide for the real-PC test | - |

## Windows components

| Component | Implemented | Automated tests | CI (real Windows runner) | Real PC / real 360° | Notes |
|---|---|---|---|---|---|
| State machine + confirmation gate | ✅ | ✅ 33 incl. property-based + races | ✅ | ❌ | only `approve_question` enters EXECUTING |
| Composite confidence | ✅ | ✅ | ✅ | ❌ | |
| Question cache | ✅ | ✅ | ✅ | ❌ | |
| AI providers + resilience | ✅ | ✅ fake clients | ✅ SDKs bundled | ❌ | **no live API call** |
| Windows OCR (WinRT) | ✅ | ✅ native | ✅ benchmark below | ❌ | German OCR language pack needed (guide) |
| Tesseract OCR (fallback) | ✅ | ✅ Linux | ➖ not on runner | ❌ | |
| Extractor + checkbox detection | ✅ | ✅ | ✅ boxes found on real rendering | ❌ | real 360° layout unknown → calibration |
| Window detection / capture / capture exclusion | ✅ | ✅ native | ✅ | ❌ | |
| SendInput click + covered-target guard | ✅ | ✅ native | ✅ "Selected and verified (1 attempt)" in safe mode | ❌ | |
| Safe mode / dry run / emergency stop | ✅ | ✅ | ✅ native dry run: no input sent | ❌ | defaults: safe mode **on**, dry run **on** |
| Hotkeys (RegisterHotKey) | ✅ | ✅ native (injected F8) | ✅ | ❌ | Ctrl+Shift+X always registered |
| Credential Manager | ✅ | ✅ native | ✅ | ❌ | |
| Overlay / dashboard / onboarding / calibration | ✅ | ✅ pytest-qt | ✅ offscreen | ❌ | never seen on a real screen by a person |
| Session trace / protocol / metrics / diagnosis ZIP | ✅ | ✅ | ✅ incl. installed app `--diagnose` | ❌ | |
| Installer | ✅ | ➖ | ✅ build, silent install, installed self-test + diagnose, Start-menu entry, silent uninstall, removal | ❌ | unsigned → SmartScreen |

### What a GitHub runner cannot prove (documented, not faked)
* **The real 360° online software.** It is licensed and requires a login.
* **A person looking at the screen.** That rules out checking the overlay, the dry-run crosses and the
  interactive installer/SmartScreen.
* **Your hardware.** That covers DPI scaling ≠ 100 %, multiple monitors and audio. The runner has a single
  1024×768 virtual display at 96 DPI.
* **Long-term stability on Windows.** The 30-minute soak test ran on Linux only.

## iOS

| Component | Implemented | CI (macos-15) | iPhone | Notes |
|---|---|---|---|---|
| Smart360Core (17 XCTests) | ✅ | ✅ `swift test` | ❌ | |
| SwiftUI app, Vision OCR, URLSession providers | ✅ | ✅ simulator + device build (unsigned), `xcodebuild analyze` clean | ❌ | never launched |
| Broadcast + Share extension, App Intent | ✅ | ✅ build | ❌ | extensions need a paid Apple account |
| Live Activities | ❌ | ➖ | ❌ | not built (needs an own push server) |

## Measurements
All values come from CI run 36819103066 (commit `6f58fed`) or the container. **No value comes from a real PC.**

| Metric | Value | Where |
|---|---|---|
| Linux tests | **197 passed** (real Tesseract OCR), ruff ✅, mypy ✅ (65 files), bandit 0 medium/high, pip-audit: no known vulnerabilities | CI ubuntu-24.04 |
| Windows tests | unit/integration step green (Tesseract-only tests skipped); **11/11 native tests passed** | CI windows-latest |
| Native E2E, safe mode | real window → capture → Windows OCR → approval → SendInput → **"Selected and verified (1 attempt)"**; checkboxes found = True for all 3 answers | CI windows-latest |
| Native dry run | planned (440, 276) and (440, 356) - the same points the real-click test clicked successfully; **no input reached the window** | CI windows-latest |
| Windows OCR benchmark (120 screens) | detected **97.5 %**, answer sets exact **81.7 %**, clean screens **100 % / 100 %**, JPEG 95 % / 90 %, blur 97.5 % / 55 % (misses: heavy blur at 75 % scaling); median **55 ms**, p95 87 ms | CI windows-latest |
| Checkbox detection (simulator, 4 scalings × clean/JPEG/blur) | **144/144 found**, 0 found-but-wrong | container (Tesseract) |
| Installer | `360SmartSetup.exe` 75 423 157 bytes; silent install ✅, installed `--self-test --demo` exit 0 ✅, installed `--diagnose` ZIP ✅, Start-menu "360 SMART - Diagnose erstellen" ✅, silent uninstall exit 0 + files and registry entry removed ✅ | CI windows-latest |
| Soak test (30 min, earlier build, Linux) | 1 215 correct selections, 0 wrong, 0 errors, RSS plateau ~80 MB | container |
| **Real-PC metrics** (OCR accuracy on 360°, E2E success, false clicks, latency with a real AI) | **not measured yet** - produced by the 50-question test in REAL_DEVICE_TEST.md | - |

## Where the Windows installer is
* **GitHub pre-release v0.5.0-alpha.3:** https://github.com/R8-CRT7/R8/releases/tag/v0.5.0-alpha.3. It is
  built by the release run of `windows.yml`, which repeats every test before it publishes. Assets:
  `360SmartSetup.exe` and `360SmartSetup.exe.sha256`.
* Older: v0.5.0-alpha.2 and v0.5.0-alpha.1 (without the safety work of this phase).
* Every green `windows.yml` run also keeps the artifact **360SmartSetup** for 90 days.

## Open before 1.0
1. **The real-PC test (`REAL_DEVICE_TEST.md`)** with the real 360° online software. This means:
   calibration, the dry run on 10 questions, real clicks, the safety tests and the 50-question protocol.
   Then evaluate the diagnosis ZIP and fix what it shows.
2. **One live API call per provider** with your key, plus the real costs per question.
3. **iPhone test.** Needs your Apple ID; the extensions need a paid account.
4. A 60-minute soak test on Windows, and multi-monitor and 125 %/150 % scaling on real hardware.
5. Optional: a code-signing certificate (removes the SmartScreen warning).
