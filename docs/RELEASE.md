# Release

## Versions
`0.1 development` → **`0.5 alpha` (current: 0.5.0-alpha.3)** → `0.9 beta` → `1.0` only when the checklist
below is fully green, including tests against the real 360° online software and on a real iPhone.

## Windows build
Automated: `.github/workflows/windows.yml`.
* On `ubuntu-24.04`: ruff, mypy, all tests with real Tesseract, bandit, and pip-audit (blocking).
* On `windows-latest`:
  1. unit, integration and UI tests;
  2. native Windows tests: real window, capture, Windows OCR (including concurrent calls), SendInput,
     hotkeys, Credential Manager, and the covered-target guard;
  3. the Windows OCR benchmark;
  4. PyInstaller onedir build;
  5. `--self-test --demo` of the frozen exe;
  6. Inno Setup → `dist/360SmartSetup.exe`, plus a SHA-256 file;
  7. silent install and self-test of the installed app;
  8. **silent uninstall**, then a check that the files and the HKCU uninstall entry are gone;
  9. upload of the artifact **360SmartSetup**;
  10. a job summary with the native test output, the OCR benchmark and the installer hash.
* **Publishing a pre-release:** *Actions → windows (tests, native, installer) → Run workflow* with
  `release_tag` (e.g. `v0.5.0-alpha.3`). The `release` job attaches the CI-built installer and its checksum
  to a GitHub pre-release, with `docs/RELEASE_NOTES.md` as the text.

Manual: `powershell -ExecutionPolicy Bypass -File windows\packaging\build.ps1` (Python 3.11+ and Inno Setup 6
on the build machine only - end users need neither).

**Code signing (optional, costs money):** an OV/EV code-signing certificate (typically ~100–400 €/year) or
Azure Trusted Signing (~10 $/month) removes the SmartScreen "unknown publisher" warning. Not included.

## iOS build
Automated: `.github/workflows/ios.yml` on `macos-15` (Xcode 16.4, iOS 18.5 SDK):
* `swift test` for Smart360Core (17 tests);
* XcodeGen, then an unsigned simulator build of the app and both extensions;
* `xcodebuild analyze`, which fails the job on analyzer findings;
* an unsigned build for a real device (arm64);
* the free-account project variant;
* SwiftLint (informational).

Signing and installing on an iPhone cannot run in CI without the user's Apple ID.

Device install:
1. `brew install xcodegen && cd ios && xcodegen generate` (paid account) or `--spec project-free.yml` (free).
2. Open `Smart360.xcodeproj` → target *Smart360* (and both extensions) → *Signing & Capabilities* → Team.
3. Paid account: Xcode registers the App Group `group.com.smart360.app` and the keychain group automatically.
   If the bundle ids are taken, change `com.smart360.*` in `project.yml` (all three targets + `AppGroup.identifier`
   in `Platform.swift`).
4. Connect the iPhone, enable *Developer Mode* (Settings → Privacy & Security), Run.
5. Trust the developer: Settings → General → VPN & Device Management.

**Costs:** Apple Developer Program 99 €/year (needed for the broadcast/share extensions and for apps that
don't expire). Free account: app only, re-install every 7 days, max. 3 sideloaded apps.
App Store / TestFlight distribution is possible with the paid account but was not prepared (review of
"answers questions of a third-party learning app" is uncertain).

Permissions requested: Photos (only the picked screenshot), Notifications (live results). Screen broadcast
is started explicitly by the user through the system picker (red status bar while active).

## Release checklist

| Item | State (0.5.0-alpha.3) |
|---|---|
| Windows app starts | ✅ frozen exe + installed app `--self-test --demo` on windows-latest (CI) |
| Overlay works | ✅ UI tests on Windows (offscreen) + rendered screenshots; ❌ not yet seen on a real desktop by a person |
| Question detection works | ✅ real Windows window + capture + Windows OCR (CI); ❌ not yet on real 360° online |
| AI works | ✅ Mock/demo end-to-end; ❌ no live API call made (no key available) |
| Confirmation required | ✅ enforced + tested (unit, property, race, engine, app, native E2E) |
| Safe mode / dry run / emergency stop | ✅ tested incl. native; defaults on; ❌ not yet on a real PC |
| Diagnosis ZIP without secrets | ✅ tested (planted key/password/token absent), installed-app `--diagnose` in CI |
| No stale action execution | ✅ tested (question change during approval / before click / window lost) |
| Cache works | ✅ |
| Settings persist | ✅ |
| Recovery works | ✅ AI offline, invalid JSON, capture failures, corrupt files, internal exceptions |
| UI responsive | ✅ UI-lag health, all work off the UI thread |
| Installer works | ✅ built, silently installed, self-tested, silently uninstalled (CI); ❌ interactive install on a user PC |
| iOS builds | ✅ simulator + device (unsigned) + analyze (CI); ❌ not signed / installed on an iPhone |
| iOS workflow documented | ✅ |
| No critical test failures | ✅ Linux 197 · Windows all + 11/11 native · iOS 17 XCTests |
| No exposed secrets | ✅ redaction tests, bandit, pip-audit, no keys in repo |
| Docs complete | ✅ |
