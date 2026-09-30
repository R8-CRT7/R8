# 360 SMART 0.5.0-alpha.2 (pre-release)

**Alpha.** Built and verified automatically on a GitHub `windows-latest` runner. It has **not** yet been
tested against the real 360° online software or on real user hardware. See `docs/FINAL_STATUS.md`.

## Download
* `360SmartSetup.exe`: per-user installer, no admin rights, and no Python needed on the target PC.
* `360SmartSetup.exe.sha256`: checksum. Check it with `Get-FileHash 360SmartSetup.exe` in PowerShell.

The installer is **unsigned**, so Windows SmartScreen shows "Windows protected your PC". Click
*More info → Run anyway*. The fix is a paid code-signing certificate (see `docs/RELEASE.md`).

## What was verified in CI for this build
* 162 unit, integration and UI tests. Linux runs them with real Tesseract OCR; Windows runs them too.
* Native Windows tests on the real desktop:
  * DPI awareness
  * Windows OCR on a rendered question, including 8 concurrent calls
  * window detection and capture exclusion
  * Credential Manager
  * RegisterHotKey via an injected F8
  * a real capture → Windows OCR → confirmation → SendInput click → verification run
  * the covered-target click guard
* PyInstaller build and frozen `--self-test --demo`.
* The installer build, silent install, self-test of the installed app, silent uninstall, and a check
  that the files and the registry entry were removed.

## Changes since alpha.1 (found by CI on real Windows)
* **Windows OCR:** checkbox glyphs ("C]", "Cl", "Ü") are no longer read as part of the answers. Answer sets
  read exactly went from 45 % to 81.7 % in the benchmark, and to 100 % on clean screens.
* **Windows OCR:** there is one OCR engine per thread. Parallel question and answer OCR used to fail.
* **Confidence:** the "model uncertain" cap is monotone again.

## Windows OCR benchmark (CI, 120 simulator screens)
The benchmark found **97.5 %** of the questions and read **81.7 %** of the answer sets exactly, at a median
of **79 ms**. On clean screens it read 100 % of the answer sets exactly.

## Known limitations
* No live AI call has been made (no API key was available). Demo mode uses the offline practice simulator.
* The checkbox and region layout of the real 360° online software is unknown. Use the calibration wizard.
* iOS is source only (Xcode project) and is not part of this download.
