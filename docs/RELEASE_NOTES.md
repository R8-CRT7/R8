# 360 SMART 0.5.0-alpha.3 (pre-release) – ready for the first real-PC test

**Alpha.** Built and verified automatically on GitHub runners. It has **not** yet been tested against the real
360° online software, on your own PC or with a real AI key. **Start here:**
[REAL_DEVICE_TEST.md](https://github.com/R8-CRT7/R8/blob/claude/360-smart-ai-assistant-a4bd4h/REAL_DEVICE_TEST.md)

## Download
* `360SmartSetup.exe`: per-user installer, no admin rights, no Python needed.
* `360SmartSetup.exe.sha256`: checksum (`Get-FileHash 360SmartSetup.exe` in PowerShell).

The installer is **unsigned**, so SmartScreen shows "Windows protected your PC". Click *More info → Run anyway*.

## Safe by default
* **Dry run is on.** The app does everything up to the click and shows **where** it would click (red cross on
  screen + message), but clicks nothing. You switch it off in *Settings → Safety*.
* **Safe mode is on.** There is no click when:
  * the confidence is low,
  * a checkbox was only estimated,
  * the target is ambiguous,
  * the checkbox state can't be read,
  * the window moved, or another window covers the answer.

  Failed clicks are not retried.
* **Emergency stop:** `Ctrl+Shift+X` (always works), the STOP button or the tray menu. It shows STOPPED and
  drops pending clicks.

## New for the real test
* **Create diagnosis (ZIP)**: dashboard → *Diagnostics*, the tray menu, or *Start menu → 360 SMART - Diagnose
  erstellen*. It contains versions, Windows/monitor/DPI info, the detected window, OCR results, confidence,
  click coordinates, state changes, logs and per-question traces. It contains **no** API keys, passwords or
  tokens.
* **Per-question trace and test protocol** (`protocol.csv` + metrics) for the 50-question test.

## Fixed (found by new regression tests)
* With an unreadable checkbox state the app used to click and then click again on retry, toggling the box
  back. Now it never clicks without a readable state.
* An approved answer that matched two answers on screen used to click the first one. Ambiguous targets are
  now refused.
* Checkboxes are now really detected (a square outline) instead of estimated. On the simulator 144 of 144
  were found, with no false positives.

## Known limitations
* No live AI call has been made yet.
* The layout of the real 360° online software is unknown, so calibrate it (guide, part 5.2).
* iOS is source only and not part of this download.
