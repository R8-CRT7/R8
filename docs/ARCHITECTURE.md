# Architecture

## Repository layout

```
windows/                     Python 3.11+ · PySide6 desktop app
  smart360/
    core/                    models, state machine, confidence engine, imaging, question identity
    ai/                      provider interface, Anthropic/OpenAI/Gemini/Mock, schema, resilience
    vision/                  OCR backends, question extractor, checkbox reader
    capture/                 capture targets (window/region/simulator), change detection, simulator
    engine/                  orchestrator + input drivers
    platform/win32.py        DPI, window detection, SendInput, hotkeys, capture exclusion (ctypes)
    storage/                 config (atomic + recovery), secrets (keyring), cache, history, paths
    health/                  health monitor, watchdog, self-test, diagnostic export
    ui/                      Neural Glass UI: theme, widgets, overlay, dashboard, pages, onboarding, calibration
    services.py · app.py     service container · entry point / controller
  tests/                     unit, property-based, integration (real OCR), UI (pytest-qt), native Windows
  tools/                     screenshots, OCR benchmark, soak test, icon generator
  packaging/                 PyInstaller spec, Inno Setup script, build.ps1
ios/
  Packages/Smart360Core/     Swift package: models, state machine, cache, confidence, schema, providers, analyzer
  Smart360/                  SwiftUI app (design system, screens, app model, App Intent)
  Smart360Broadcast/         ReplayKit broadcast upload extension (live analysis)
  Smart360Share/             share extension
  project.yml / project-free.yml   XcodeGen specs (paid / free Apple account)
docs/                        this documentation
.github/workflows/           windows.yml (Linux quality + Windows native + installer), ios.yml (macOS)
```

## Windows data flow

```
┌──────────── engine thread (serialises every decision) ────────────┐
│ locate window ─► grab question+answers band ─► ChangeDetector      │
│      (TargetLost → abandon question)          (settled change?)    │
│                                  ▼                                  │
│   begin_capture() → generation+1, approvals void                   │
│   grab client area ─► QuestionExtractor (OCR, answers, checkboxes, │
│                        image dHash, clarity) ─► question_detected  │
│                                  ▼                                  │
│   same question as before? keep prediction : submit analysis ──────┼──► analysis worker
│                                                                     │     cache.lookup (safe)
│   ◄──── "analysis_done"(question, generation, prediction) ─────────┼──── or ResilientSolver
│   stale? drop.  else publish prediction → answer_ready()            │     (retry, timeout, breaker,
│                  → WAITING_FOR_CONFIRMATION                         │      dedup) → provider
│                                                                     │     → schema validation
│   ◄──── UI command "approve"(question_id) ─────────────────────────┤     → composite confidence
│   approve_question() → EXECUTING + ApprovalToken                    │
│   consume token → fresh capture → same question? (fuzzy identity)   │
│   → answers by TEXT → current checkbox states → click difference   │
│     (atomic SendInput, window-under-point check, token re-checked)  │
│   → VERIFYING (fresh capture, states == approval) → retry ≤ 3       │
│   → WAITING_FOR_NEXT_QUESTION                                       │
└─────────────────────────────────────────────────────────────────────┘
          │ events (EngineBridge: Qt signals, queued) ▼
     UI thread: overlay · dashboard · hotkeys · tray   (never blocks)
```

## State machine (hard safety rule)

States: `WAITING_FOR_QUESTION, CAPTURING, ANALYZING, ANSWER_READY, WAITING_FOR_CONFIRMATION,
EXECUTING_CONFIRMED_ACTION, VERIFYING, WAITING_FOR_NEXT_QUESTION, PAUSED, ERROR`.

* The transition table has **no** edge into `EXECUTING_CONFIRMED_ACTION`.
* `transition(EXECUTING_…)` raises unconditionally.
* `approve_question(question_id)` is the only entry: requires `WAITING_FOR_CONFIRMATION`, the current
  question id and generation; returns a single-use `ApprovalToken`.
* Every capture, pause, error or abandoned question bumps the generation → outstanding tokens die.
* The executor presents the token before every input and re-checks it between clicks.
* `retry_execution` re-enters EXECUTING only from VERIFYING with the same token, max 3 attempts.

Tests: static table check, every state × generic transition, wrong id, stale generation, pause during
analysis/execution, approval exactly while the question changes (engine-level and state-machine race with
threads), 16 concurrent approvals (exactly one wins), 400-case property-based random walk.

## Question identity & cache safety

`core/matching.py::same_question` and `storage/cache.py` share the rules: same type, equal number tokens,
≥ 95/97 % similarity **without word insertions** (catches "nicht"), 1:1 answer mapping, compatible image
hashes. Resize/re-render keeps identity; a changed question never does.

## Confidence

`final = weighted geometric mean(model 0.50, OCR 0.18, layout 0.12, image clarity 0.08 (if image),
question match 0.07 (reserved - currently always 1.0, not yet fed by the engine), cache similarity 0.05
(if cache))`, capped when OCR < 55 % or layout < 50 %
(max 60 %), and below the threshold when the model says `uncertain`. Below the threshold → **MANUAL CHECK**:
ENTER is disabled, the button reads *CONFIRM ANYWAY*.

## Change detection & adaptive polling

160×90 grayscale signature of the question+answers band (~1.7 ms). A change is a mean difference ≥ threshold
**or** ≥ 1 % of pixels changed by > 24 grey levels (the mean alone missed two similar text-only questions);
it must be stable for 2 frames.
Polling: 150 ms while settling, 350 ms normal, 1.2 s after 20 s idle. The AI is only called for a new,
settled screen that is not the same question (manual ticks re-use the prediction) and not in the cache.

## Health & recovery

Components: Capture, Vision, AI, Input, Cache, Network, UI → HEALTHY / DEGRADED / RECOVERING / FAILED.
Self-recovery: the engine loop catches every exception; errors enter `ERROR` with exponential back-off
(1 s → 30 s) and recover automatically; the AI circuit breaker opens after 4 failures for 30 s (one probe
in half-open); OCR calls are bounded by a 15 s timeout; config/cache/history files are quarantined and
rebuilt when corrupted. Watchdog: CPU, RSS, RSS trend (least squares, MB/h), threads, UI event lag.

## Overlay

Frameless, translucent, tool window, always-on-top (pinnable), `WA_ShowWithoutActivating` (never steals
focus from the browser), `SetWindowDisplayAffinity(WDA_EXCLUDEFROMCAPTURE)` so it never appears in its
own screen captures. Modes: FULL · FOCUS (answer + confidence pill) · ORBIT (a single Neural Pulse orb).

## iOS

`Smart360Core` (pure Swift, unit-tested) is shared by the app and both extensions through an App Group
container (cache, history, settings) and a keychain access group (API key). The phone app's layout is not
calibrated, so the model also extracts question/answer texts (structured output) while Vision OCR feeds the
cache and change detection. The broadcast extension samples ≤ 1 fps, detects settled changes with a 9×8
dHash, OCRs on-device and notifies; it stays under the ~50 MB extension limit by downscaling immediately and
keeping no frame history.
