# Release

## Versions
`0.1 development` → **`0.5 alpha` (current: 0.5.0-alpha.1)** → `0.9 beta` → `1.0` only when the checklist
below is fully green, including tests against the real 360° online software and on a real iPhone.

## Windows build
Automated: `.github/workflows/windows.yml` on `windows-latest`:
1. unit + integration + UI tests, 2. native Windows tests (real window, capture, Windows OCR, SendInput,
hotkeys, Credential Manager, covered-target guard), 3. PyInstaller onedir build, 4. self-test of the frozen
exe, 5. Inno Setup → `dist/360SmartSetup.exe`, 6. silent install + self-test of the installed app,
7. upload artifact **360SmartSetup**.

Manual: `powershell -ExecutionPolicy Bypass -File windows\packaging\build.ps1` (Python 3.11+ and Inno Setup 6
on the build machine only - end users need neither).

**Code signing (optional, costs money):** an OV/EV code-signing certificate (typically ~100–400 €/year) or
Azure Trusted Signing (~10 $/month) removes the SmartScreen "unknown publisher" warning. Not included.

## iOS build
Automated: `.github/workflows/ios.yml` on `macos-15`: `swift test` for Smart360Core, XcodeGen, unsigned
simulator build of the app + both extensions.

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

| Item | State (0.5.0-alpha.1) |
|---|---|
| Windows app starts | ✅ Linux offscreen smoke; ⏳ Windows CI (needs repo push access) |
| Overlay works | ✅ rendered + UI tests; ⏳ on a real Windows desktop |
| Question detection works | ✅ simulator + real Tesseract OCR; ❌ not yet on real 360° online |
| AI works | ✅ Mock/demo end-to-end; ❌ no live API call made (no key available) |
| Confirmation required | ✅ enforced + tested (unit, property, race, engine, app) |
| No stale action execution | ✅ tested (question change during approval / before click / window lost) |
| Cache works | ✅ |
| Settings persist | ✅ |
| Recovery works | ✅ AI offline, invalid JSON, capture failures, corrupt files, internal exceptions |
| UI responsive | ✅ UI-lag health, all work off the UI thread |
| Installer works | ⏳ built + silent-installed in CI once pushed |
| iOS builds | ⏳ macOS CI once pushed (Swift syntax-checked only) |
| iOS workflow documented | ✅ |
| No critical test failures | ✅ 144 passed (Linux); native Windows + iOS suites pending CI |
| No exposed secrets | ✅ redaction tests, bandit, no keys in repo |
| Docs complete | ✅ |
