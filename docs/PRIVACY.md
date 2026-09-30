# Privacy

**Principle: collect nothing that is not needed; keep everything local; send only the current question.**

| Data | Where | How long | Leaves the device? |
|---|---|---|---|
| Screen captures | RAM only | discarded after analysis | Only crops of the **current question** (question/answers/situation image, downscaled) go to the AI provider you chose |
| Debug screenshots | `%APPDATA%\360Smart\debug` | last 50 frames | no · **off by default** |
| Question cache (text, answers, prediction) | local SQLite / JSON | until cleared (max 20 000 entries) | no |
| History (question, recommendation, confidence, decision) | local SQLite / JSON | 90 days (configurable), can be cleared | no |
| Question text in history | local | optional (*Store question text* toggle) | no |
| API keys | Credential Manager / Keychain | until removed | only to the provider in the auth header |
| Diagnostics report | only when you export it | – | only if you share it; contains no keys, texts or images |
| Telemetry / analytics | **none** | – | – |

* iOS live broadcast frames are processed in memory by the extension; only the downscaled current screen
  of a *new* question is sent to the AI.
* The AI providers' own data policies apply to what is sent to them (e.g. retention for abuse monitoring).
  Choose the provider accordingly.
* Uninstalling keeps `%APPDATA%\360Smart` and the stored key so a reinstall keeps your setup; delete the
  folder and the *360Smart* credential to remove everything.
