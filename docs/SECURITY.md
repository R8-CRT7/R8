# Security

## Secrets
* **Windows:** API keys in the Windows Credential Manager via `keyring` (WinVault backend). The AI page shows
  where the key is stored; if no secure store exists the key is kept in memory only and the UI says so.
  `.env` / environment variables are honoured for development only.
* **iOS:** Keychain (`kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly`), shared with the extensions via a
  keychain access group; never written to files or UserDefaults.
* **Logs:** every log record passes `RedactingFilter` (Anthropic/OpenAI/Google key patterns, `api-key`,
  `authorization` headers). Diagnostic exports are redacted again and contain no question texts or screenshots.
  Tested (`test_redaction`, `test_logging_filter_redacts`, `test_services_demo_selftest_and_report`).

## Untrusted input
* **Model output is untrusted.** Provider-native structured outputs plus pydantic/Codable validation
  (range checks, unique 1-based indices, numeric-only number answers, max lengths, unknown topics
  normalised). Invalid output is retried, never executed.
* **OCR text is untrusted.** It is only used as model input and for matching; it never reaches a shell,
  SQL (parameterised queries; `LIKE` wildcards escaped) or file path.
* **Config files** are schema-validated; corrupted files are quarantined, never partially applied.
* **Title patterns** (user regex) are compiled and validated before saving.

## Input injection safety (Windows)
* Only after `approve_question` with a valid single-use token; re-verified before every click.
* Atomic `SendInput` (move + down + up in one batch); the click is refused if another window lies under
  the target point (`WindowFromPoint` == learning window), so nothing lands on the overlay or other apps.
* `SendInput` failures (UIPI, secure desktop) are reported, never retried blindly (max 3 attempts total).

## Files & storage
* Data under `%APPDATA%\360Smart` (per-user). Atomic writes (temp file + `os.replace` + fsync) for config.
* Screenshots are never written to disk unless *Debug screenshots* is enabled (last 50 frames, local).
* iOS files use `.completeFileProtection`.

## Network
* HTTPS only, to the selected provider. No telemetry, no update pings, no analytics.
* SDK retries disabled; our resilience layer limits retries (≤ 5), backs off and opens a circuit breaker.

## Supply chain
* Runtime dependencies (Windows): PySide6, pydantic, numpy, Pillow, mss, rapidfuzz, anthropic, keyring,
  psutil (+ optional openai, google-genai, winrt-*; the tesseract binary is called directly with a fixed argv, no shell). iOS: none (Apple frameworks only).
* `pip-audit` (2026-09-30): no known vulnerabilities in runtime dependencies; the only finding was
  `setuptools 79` (build tool only) → build requirement raised to `setuptools>=83`.
* `bandit -ll`: 0 medium/high findings; 5 low-severity intentional `try/except/pass` (listener isolation,
  best-effort cleanup).
* CI runs ruff, mypy, bandit and pip-audit on every push.

## Known limitations
* The Windows installer is **not code-signed** (certificate costs money) → SmartScreen warning.
* `ENTER`/`ESC` are registered as global hotkeys while a question awaits confirmation; another app that
  already owns them wins (reported in Diagnostics).

## Reporting
Please open a private security advisory on the repository.
