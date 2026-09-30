# Testing

## Running

```bash
cd windows
QT_QPA_PLATFORM=offscreen pytest                 # 144 tests (~65 s)
pytest -m windows tests/test_windows_native.py   # on Windows, QT_QPA_PLATFORM=windows (CI does this)
python tools/soak.py --minutes 30                # soak / memory
python tools/ocr_benchmark.py                    # OCR accuracy + latency
python tools/screenshots.py                      # visual review of every screen
cd ../ios/Packages/Smart360Core && swift test    # iOS core (macOS)
```

## Suites

| Suite | File | What it proves | # |
|---|---|---|---|
| State machine | `test_state_machine.py` | the confirmation gate: static table, every state, stale ids/generations, pause, races (16 threads, approve-vs-capture ×200), 400-case property-based random walk | 33 |
| Cache & confidence | `test_cache_confidence.py` | cache never answers a different question (numbers, negation in long questions, images, answer sets, type), shuffle remap, corruption recovery, eviction; confidence bounds/monotonicity (property-based) | 23 |
| AI layer | `test_ai.py` | schema rejects free text / out-of-range / duplicates; request shapes for Anthropic (structured outputs, effort, fallbacks), OpenAI, Gemini; SDK error mapping; retry, timeout, circuit breaker (closed/open/half-open), dedup, crash containment, cost tracking | 29 |
| Engine integration | `test_engine_integration.py` | full loop on the simulator with **real Tesseract OCR**: detection → AI → confirmation → click → verification; shuffled answers; next question; plus the race/chaos cases below | 23 |
| Storage & services | `test_storage_services.py` | config roundtrip/backup/quarantine, secret redaction, history filters (LIKE escaping), privacy mode, retention, health states, leak-slope maths, self-test, report contains no key/question text | 17 |
| UI | `test_ui.py` | overlay states/modes/signals, Neural Pulse states, all 9 dashboard pages, history filters/empty state, calibration wizard (mouse-drag → valid profile), onboarding flow, **whole app demo round-trip incl. ENTER blocked on manual check**, UI-lag health, single-instance lock | 10 |
| Chaos / bug hunt | `test_chaos.py` | invalid/degenerate profiles, 1-px and full-window regions, crashing OCR, empty OCR, cache/config deleted while running, wrongly typed config, unknown forced profile | 9 |
| Native Windows | `test_windows_native.py` | DPI awareness, Windows OCR on a rendered screen, window detection + capture exclusion, Credential Manager, RegisterHotKey via injected F8, real capture + Windows OCR + SendInput end-to-end, click refused when a window covers the target | 7 (CI) |
| iOS core | `CoreTests.swift` | state machine, normalisation/numbers, ratio definition, negation guard, cache safety + remap + corruption, schema validation, Anthropic body shape, confidence caps, phone screenshot parser, frame hash | 16 (CI) |

## Race-condition & chaos cases (engine level)

| Case | Test | Expected (verified) |
|---|---|---|
| Confirmation exactly while the question changes | `test_confirmation_exactly_when_question_changes_is_not_executed` | nothing clicked |
| Question changes between approval and click | `test_question_changes_between_approval_and_click` | refused, nothing clicked |
| Two AI responses / stale prediction | state machine tests | only the current one counts |
| Pause during analysis | `test_pause_during_analysis_drops_result` | result dropped, stays paused |
| Window disappears during analysis / during click | `test_window_disappears_*` | question abandoned / execution fails safely |
| Window moved + resized | `test_window_moved_and_resized` | identity kept, correct click |
| Click swallowed | `test_lost_click_is_retried_and_verified` | retried, verified |
| Click never lands | `test_max_three_attempts` | stops after 3, history = failed |
| Network loss / AI offline | `test_ai_offline_then_recovers` | ERROR "AI OFFLINE" → breaker → recovery |
| Invalid JSON from AI | `test_invalid_json_from_ai_is_not_executed` | never executed |
| Screenshot failures | `test_screenshot_failures_are_contained` | health DEGRADED, continues |
| Hotkey spam (approve/pause ×25) | `test_hotkey_spam_executes_once` | ≤ 1 execution |
| Internal exception in the loop | `test_engine_survives_internal_exception` | loop survives |
| Corrupt config / cache / history | storage tests | quarantined, defaults, app starts |
| User ticks a box manually | `test_manual_tick_keeps_prediction_and_exec_fixes_selection` | no new AI call; exact selection set |
| Number question | `test_number_question_is_advisory_by_default` | advisory unless flag enabled |

## Visual review
`tools/screenshots.py` renders overlay (5 states × 3 modes), all 9 dashboard pages with live engine data,
splash, onboarding (6 steps) and calibration. Reviewed by eye; fixes made: KPI grid column widths, health
header, answer wrapping, sidebar status eliding, history topic column, provider card text wrapping, welcome
text clipping, calibration panel placement, self-test ghost rows, orbit icon, context-aware key hints.

## Findings from testing (all fixed)
* Cache: a long question with an inserted "nicht" matched at 98.5 % → word-level guard.
* Engine: resize/re-render changed the exact fingerprint → fuzzy identity (`same_question`).
* Engine: event helper crashed on a payload field named `kind` (found by the AI-offline test).
* Engine: state became WAITING_FOR_CONFIRMATION before the prediction was published.
* Vision: concurrent Tesseract calls oversubscribed the CPU (load 85, calls > 10 min) → one OpenMP thread
  per process + 15 s timeout.
* Secrets: unusable keyring backends were reported as secure.
* Windows click path (review): non-atomic move+click; clicks could land on a window covering the target.
* App (bug hunt): a second instance would run a second engine → single-instance lock.

## Soak / memory
See `docs/FINAL_STATUS.md` → *Soak test* for the 30-minute run (cycles, RSS trend, errors).
