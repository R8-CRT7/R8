# Research log (2026-09-30)

Sources: web search, GitHub (MCP search API), official docs (Apple Developer, Anthropic docs via the
bundled Claude API reference), PyPI. Star counts / activity as reported by the GitHub API on 2026-09-30.

## Target software
* **360° online / CLICK & LEARN 360° online (DEGENER)** runs as Android/iOS app and **as a desktop
  version in the browser** ([degener.de](https://www.degener.de/service-und-support/software-informationen/click-learn-360-online/)).
  ⇒ On Windows the "window" is a browser tab → window detection by title (browser process), layout profiles
  relative to the client area, and a calibration wizard as fallback. The real UI is behind a login and was
  **not available** during development → a self-written 360°-style simulator is used for tests.

## Libraries evaluated

| Name | URL | Purpose | Lang | License | ★ | Last update | Why useful | Risks | Use? |
|---|---|---|---|---|---|---|---|---|---|
| PySide6 | pypi.org/project/PySide6 | UI | Py/C++ | LGPLv3 | – | 6.11.2 (2026) | custom painting, overlays, offscreen testing | size (~100 MB) | **USE** |
| python-mss | github.com/BoboTiG/python-mss | screen capture | Py | MIT | 1.3k | 2026-09 | pure ctypes, fast, cross-platform | none relevant | **USE** |
| windows-capture | github.com/NiiightmareXD/windows-capture | WGC capture | Rust/Py | MIT | – | 2026 | fastest, GPU | extra native dep; mss is fast enough for ~2 fps | do not use (now) |
| RapidFuzz | github.com/rapidfuzz/RapidFuzz | fuzzy matching | C++/Py | MIT | 4.1k | 2026-09 | fast `ratio`, used by cache/identity | none | **USE** |
| imagehash | github.com/JohannesBuchner/imagehash | pHash/dHash | Py | BSD | – | – | perceptual hashes | pulls SciPy/PyWavelets | do not use – dHash is 15 lines with numpy |
| pywinauto | github.com/pywinauto/pywinauto | UIA automation | Py | BSD | 6.2k | 2026-09 | UIA tree of browser pages | heavy (comtypes), slow for browsers | do not use (UIA text source = future flag) |
| winrt-Windows.Media.Ocr | pypi (pywinrt) | Windows OCR | Py | MIT | – | 2.x | built-in OCR, offline, fast | no per-word confidence | **USE** (primary on Windows) |
| winocr | github.com/GitHub30/winocr | Windows OCR wrapper | Py | MIT | 25 | 2026-08 | reference for WinRT OCR usage | small project | reference only |
| Tesseract (CLI) | github.com/tesseract-ocr | OCR | C++ | Apache-2.0 | – | – | cross-platform, confidences, CI | OpenMP oversubscription (fixed: OMP_THREAD_LIMIT=1) | **USE** (fallback + CI), called directly |
| pytesseract | github.com/madmaze/pytesseract | Tesseract wrapper | Py | Apache-2.0 | – | – | convenient | per-call unique glob pattern → fnmatch LRU cache growth (~5 KB/question, found by soak test) | **removed** – 40-line direct runner |
| PaddleOCR | github.com/PaddlePaddle/PaddleOCR | OCR | Py | Apache-2.0 | 90k | 2026-09 | very accurate | Paddle runtime ~1 GB | do not use |
| EasyOCR | – | OCR | Py | Apache-2.0 | – | – | easy API | PyTorch ~700 MB | do not use |
| PyQt/PySide Frameless-Window | github.com/zhiyiYo/PyQt-Frameless-Window | acrylic/mica | Py | GPLv3 | – | 2026 | Win11 effects | **GPL** – incompatible with a closed app | do not use (own 10-line DWM call) |
| keyring | pypi.org/project/keyring | secret storage | Py | MIT | – | 25.7 | Windows Credential Manager | none | **USE** |
| psutil | pypi | process metrics | Py | BSD | – | 7.2 | watchdog | none | **USE** |
| pydantic v2 | pypi | schema validation | Py/Rust | MIT | – | 2.13 | strict validation of AI output/config | none | **USE** |
| anthropic SDK 1.x | pypi | Claude API | Py | MIT | – | 1.9 | structured outputs, typed errors | uses `httpx2` | **USE** |
| openai / google-genai | pypi | providers | Py | Apache/MIT | – | 2026 | official SDKs | not live-tested | optional extras |
| hypothesis | pypi | property tests | Py | MPL-2.0 | – | 6.168 | state machine random walks | dev only | **USE** (dev) |
| pytest-qt | pypi | UI tests | Py | MIT | – | – | Qt tests offscreen | dev only | **USE** (dev) |
| PyInstaller | github.com/pyinstaller/pyinstaller | packaging | Py | GPL w/ exception | – | 6.x | fast builds | AV false positives (mitigated: onedir, no UPX) | **USE** |
| Nuitka | github.com/Nuitka/Nuitka | packaging | Py | Apache-2.0 | – | – | smaller, fewer AV flags | 20–40 min PySide6 builds | alternative (documented) |
| Inno Setup | jrsoftware.org | installer | Pascal | free | – | 6.x | per-user installer, German UI | – | **USE** |
| XcodeGen | github.com/yonaskolb/XcodeGen | Xcode project gen | Swift | MIT | – | 2026 | reviewable project spec, no pbxproj | Mac tool | **USE** |
| tree-sitter-swift | pypi | Swift syntax check | – | MIT | – | – | syntax-check Swift without a Mac | syntax only | used in dev |
| Inter typeface | github.com/rsms/inter | typography | – | OFL-1.1 | – | 4.1 | tabular figures, premium look | – | **USE** (bundled) |

## Platform research
* **ReplayKit broadcast upload extension:** separate process, ~50 MB memory cap, frames via
  `processSampleBuffer`; downscale + autoreleasepool recommended
  ([forasoft 2026](https://www.forasoft.com/blog/article/how-to-implement-screen-sharing-in-ios-1193)).
  ⇒ 1 fps sampling, immediate downscaling, no frame history.
* **Apple capabilities:** App Groups, Keychain Sharing, Push, Siri are **not** available to free accounts
  ([Apple: supported capabilities](https://developer.apple.com/help/account/reference/supported-capabilities-ios))
  ⇒ two project specs (paid / free).
* **Structured outputs (Claude):** `output_config.format` with `json_schema`; `output_format` is deprecated;
  Opus 5.5 rejects sampling params and disabled thinking; effort default `medium` → set `low` explicitly;
  refusal fallback via `fallbacks: "default"` + beta `server-side-fallback-2026-07-01`.
* **Current model ids** (2026-09): Anthropic `claude-opus-5-5`, `claude-sonnet-5-5`, `claude-haiku-4-5`;
  OpenAI GPT-6 family (`gpt-6-luna`, `gpt-6.1-sol`, `gpt-6-astra`); Google `gemini-3.8-flash`.
  OpenAI/Gemini ids from web search - verify in the provider console.
* **PyInstaller vs Nuitka AV behaviour:** onefile self-extraction resembles packers → onedir + installer
  ([pythonguis](https://www.pythonguis.com/faq/problems-with-antivirus-software-and-pyinstaller/)).

## Claude Code tooling
* Available and used: GitHub MCP (research), web search/fetch, the bundled *claude-api* skill (current API
  shapes and model ids), background tasks (soak test), Artifact/Docs tools (not needed).
* Not installed on purpose: extra MCP servers/plugins - nothing missing justified the added trust surface.
* Not available in this environment: Swift toolchain (download blocked by network policy), Windows, macOS,
  a real iPhone → covered by GitHub Actions runners (Windows + macOS), pending repository write access.

## Design research (principles, not copies)
Raycast (command-first density, crisp 1 px rims), Linear (quiet palette, motion only for state), Arc
(glass + colour as identity), Apple Vision Pro (depth by light/blur instead of borders), automotive HUDs
(segmented gauges, tabular telemetry, glanceability). ⇒ NEURAL GLASS: one calm canvas, glass surfaces with
rim light, cyan = "the AI speaks", violet only as secondary glow, segmented HUD confidence gauge, tabular
Inter figures, Neural Pulse as the single animated brand element.
