# Final status - 360 SMART 0.5.0-alpha.2 (2026-09-30)

**Legend.** ✅ done and verified the way the column says · ❌ not done · ➖ not applicable.
*Implemented* = code exists · *Unit tested* = automated tests on the component · *Integration tested* =
automated end-to-end test · *CI verified (real OS)* = passed on a GitHub-hosted `windows-latest` or
`macos-15` runner (a real Windows / macOS, but a virtual machine without the real 360° online software) ·
*Device verified* = on the user's own Windows PC or iPhone with the real 360° online software.

**Where it was verified.**
* Development ran in a Linux container: 162 tests with real Tesseract OCR, a 30-minute soak test, and
  screenshot review.
* GitHub Actions, green on commit `1e74200` (code) and on the release build:
  * `windows.yml`: Linux quality job + native Windows job + installer.
  * `ios.yml`: Swift tests + Xcode builds on macOS.
* **Nothing has been run on the user's own hardware or against the real 360° online software yet.** The
  "Device verified" column is therefore ❌ throughout, and that is the most important open item.

## Windows

| Component | Implemented | Unit tested | Integration tested | CI verified (real OS) | Device verified | Notes |
|---|---|---|---|---|---|---|
| State machine + confirmation gate | ✅ | ✅ 33 incl. property-based + races | ✅ | ✅ Windows runner | ❌ | only `approve_question` enters EXECUTING |
| Composite confidence engine | ✅ | ✅ | ✅ | ✅ | ❌ | monotonicity bug found by hypothesis in CI loop + fixed |
| Question cache (safe matching) | ✅ | ✅ | ✅ | ✅ | ❌ | |
| Anthropic provider (structured outputs) | ✅ | ✅ fake SDK client | ✅ via mock | ➖ | ❌ | **no live API call made** (no key) |
| OpenAI / Gemini providers | ✅ | ✅ fake clients | ➖ | ✅ SDKs bundled in installer | ❌ | not live-tested |
| Retry / timeout / circuit breaker / dedup | ✅ | ✅ | ✅ | ✅ | ❌ | |
| Tesseract OCR backend | ✅ | ✅ | ✅ real OCR | ✅ Linux runner | ❌ | not installed on the Windows runner (Windows OCR is primary) |
| **Windows OCR backend (WinRT)** | ✅ | ✅ native | ✅ real capture E2E | ✅ | ❌ | 2 bugs found on the runner + fixed (see below); benchmark below |
| Question/answer extractor + checkbox reader | ✅ | ✅ | ✅ | ✅ | ❌ | real 360° layout unknown → calibration |
| Change detection + adaptive polling | ✅ | ✅ | ✅ | ✅ | ❌ | |
| Window detection (Win32 EnumWindows) | ✅ | ✅ native | ✅ | ✅ | ❌ | |
| Screen capture (mss) + capture exclusion | ✅ | ✅ native | ✅ | ✅ | ❌ | |
| Input execution (SendInput, atomic, covered-target guard) | ✅ | ✅ native | ✅ real click E2E | ✅ | ❌ | "Selected and verified (1 attempt)" on the runner |
| Verification + max 3 attempts | ✅ | ✅ | ✅ | ✅ | ❌ | |
| Global hotkeys (RegisterHotKey) | ✅ | ✅ native (injected F8) | ➖ | ✅ | ❌ | |
| Credential Manager (keyring WinVault) | ✅ | ✅ native | ➖ | ✅ | ❌ | |
| Overlay (full / focus / orbit) | ✅ | ✅ pytest-qt | ✅ app round-trip | ✅ offscreen on Windows | ❌ | never seen on a real screen by a person |
| Dashboard (9 pages), onboarding, calibration wizard | ✅ | ✅ | ✅ | ✅ offscreen on Windows | ❌ | screenshots reviewed (Linux render) |
| Startup diagnostics / self-test / export | ✅ | ✅ | ✅ | ✅ frozen exe + installed app `--self-test --demo` exit 0 | ❌ | |
| Health monitor, watchdog, UI-lag | ✅ | ✅ | ✅ | ✅ | ❌ | |
| Config (atomic, backup, quarantine), history, insights | ✅ | ✅ | ✅ chaos | ✅ | ❌ | |
| Single-instance lock | ✅ | ✅ | ➖ | ✅ | ❌ | |
| Demo mode (practice simulator) | ✅ | ✅ | ✅ | ✅ self-test in demo mode | ❌ | |
| Sounds (optional) | ✅ | ➖ | ➖ | ➖ | ❌ | no audio device on runners |
| PyInstaller build | ✅ | ➖ | ✅ | ✅ | ❌ | |
| **Installer `360SmartSetup.exe`** | ✅ | ➖ | ✅ | ✅ build, silent install, installed self-test, silent uninstall, files + registry entry removed | ❌ | unsigned → SmartScreen warning |

### What a GitHub runner cannot prove (documented, not faked)
* **The real 360° online software.** It is a licensed product with a login. It cannot run on a public CI
  runner, so only the built-in practice simulator (same flow, own layout) was used.
* **A human looking at the overlay.** Runners have a desktop session (the native tests click real windows)
  but no one sees it. The visual review was done on rendered screenshots.
* **Interactive installer UI and SmartScreen.** The installer was run with `/VERYSILENT`. SmartScreen only
  applies to files downloaded by a browser (Mark of the Web), which is not the case on the runner.
* **Audio output**, **multi-monitor / 4K scaling** (the runner has one virtual display), and **long-term
  stability on Windows**: the 30-minute soak test ran on Linux only.

## iOS

| Component | Implemented | Unit tested | Integration tested | CI verified (real OS) | Device verified | Notes |
|---|---|---|---|---|---|---|
| Smart360Core (models, state machine, cache, confidence, schema, parser) | ✅ | ✅ 17 XCTests (`swift test`, macOS) | ➖ | ✅ macos-15 | ❌ | |
| AI providers (URLSession) | ✅ | ✅ body-shape test | ➖ | ✅ compiles | ❌ | no live call |
| SwiftUI app (6 screens, design system, Neural Pulse) | ✅ | ➖ | ➖ | ✅ Xcode 16.4 build (simulator + device arm64, unsigned) | ❌ | never launched on a simulator/phone |
| Static analysis | ➖ | ➖ | ➖ | ✅ `xcodebuild analyze`: no analyzer findings | ➖ | |
| Vision OCR | ✅ | ➖ | ➖ | ✅ compiles | ❌ | |
| Broadcast upload extension | ✅ | ➖ | ➖ | ✅ builds | ❌ | needs paid account + real device |
| Share extension | ✅ | ➖ | ➖ | ✅ builds | ❌ | needs paid account |
| App Intent (Shortcuts / Back Tap) | ✅ | ➖ | ➖ | ✅ builds (iOS 17 target; iOS-18-only API removed) | ❌ | |
| XcodeGen projects (paid / free) | ✅ | ➖ | ➖ | ✅ both generate + build | ❌ | |
| Live Activities / Dynamic Island | ❌ | ➖ | ➖ | ➖ | ❌ | not built: an extension cannot update a Live Activity without an own push server |
| Signed install on an iPhone | ❌ | ➖ | ➖ | ➖ | ❌ | needs the user's Apple ID / team (see RELEASE.md) |

## Bugs found by the CI loop (all fixed, each with a regression test)
| # | Where | Symptom | Fix |
|---|---|---|---|
| 1 | Linux mypy | numpy 2.5 stubs use PEP 695 syntax; mypy target 3.11 failed to parse them | mypy `python_version = 3.12` (shipped runtime) |
| 2 | Windows pytest | Gemini fake-client test needs `google-genai` | test skips without it; the Windows build now bundles the OpenAI + Gemini SDKs |
| 3 | iOS build | `@Parameter(supportedContentTypes:)` is iOS 18+, deployment target 17 | plain parameter, type checked in `perform()` |
| 4 | iOS free project | duplicate `Info.plist` output | exclude paid-only files |
| 5 | **Windows OCR** | "Another RecognizeAsync operation is already running!" (question + answers OCR in parallel on one engine) | one `OcrEngine` per thread; test with 8 concurrent calls |
| 6 | **Windows OCR** | empty checkbox read as "C]", inconsistently → the re-check after approval saw a "different question" and refused to click | strip box tokens |
| 7 | **Windows OCR** | checkbox read as bracket-free "Cl"/"Ü" in front of answers (benchmark: only 45 % of answer sets exact) | strip standalone glyph tokens; verbatim CI samples as tests |
| 8 | Confidence (Py + Swift) | `uncertain` cap missed values in [0.74, 0.75) → not monotone (hypothesis) | true `min()` cap |

## Measurements

| Metric | Value | Where |
|---|---|---|
| Tests | **162 passed** on Linux (real Tesseract). On Windows every test passes except 25 that need Tesseract and are skipped (Tesseract isn't installed on the Windows runner). **8/8 native Windows tests** pass. **17 XCTests** pass (`swift test`) | CI |
| Lint / types / security | ruff ✅ · mypy ✅ (61 files) · bandit: 0 medium/high · pip-audit: no known vulnerabilities (blocking) | CI |
| Windows OCR benchmark (120 screens: 4 scalings × clean/JPEG/blur) | detected **97.5 %**, answer sets exact **81.7 %** (was 45 % before fix 7) · clean screens **100 % / 100 %** · JPEG 95 % / 90 % · blur 97.5 % / 55 % (all remaining misses: heavy blur at 75 %) · median **79 ms**, p95 132 ms per question | CI windows-latest |
| Tesseract (Linux, same benchmark) | detected 93 %, answers exact 78 %, median 465 ms (docs/DECISIONS.md D-07) | container |
| Native E2E (real window → capture → Windows OCR → approval → SendInput → verify) | ✅ 1 attempt | CI |
| Installer | `360SmartSetup.exe` ≈ 75 MB, per-user, uninstall verified | CI |
| Soak test (30 min, full loop, Linux) | 1 215 correct selections, 0 wrong, 0 errors, RSS plateau ~80 MB | container |

## Where the Windows installer is
* **GitHub pre-release v0.5.0-alpha.2** (built by CI from this branch, including all fixes above):
  https://github.com/R8-CRT7/R8/releases/tag/v0.5.0-alpha.2 → asset `360SmartSetup.exe` (+ `.sha256`).
* v0.5.0-alpha.1 (https://github.com/R8-CRT7/R8/releases/tag/v0.5.0-alpha.1) is an older build without
  fixes 7–8.
* Every green `windows.yml` run also uploads the artifact **360SmartSetup** (kept 90 days):
  *Actions → windows (tests, native, installer) → run → Artifacts*.
* New pre-release: *Actions → windows → Run workflow → release_tag = v…*.

## What is needed to reach 1.0
1. **A real session with 360° online** on the user's Windows PC: install, calibrate, check detection on
   ~50 questions, and tune the checkbox reader if the real checkboxes differ.
2. **An AI key** for one live run per provider.
3. **iPhone test** (Apple ID; paid account for the extensions).
4. A 60-minute soak test on Windows. Optional: a code-signing certificate for the installer.
