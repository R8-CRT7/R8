# Manual official-source import (FeV, StVG, BKatV …)

## Status (2026-10-01): these three files are needed

Checked on 2026-10-01: gesetze-im-internet.de is not reachable from this environment (proxy) **or** from the GitHub
runner (connection timeout, knowledge-watch run #9). The RIS API (rechtsinformationen.bund.de) does not contain
FeV, StVG or BKatV yet.

Please download these **official XML files of the Federal Ministry of Justice**, unchanged, and put them into this
folder under exactly these names:

| Law | Official download (BMJ, gesetze-im-internet.de) | File name here |
|---|---|---|
| Fahrerlaubnis-Verordnung (FeV) | https://www.gesetze-im-internet.de/fev_2010/xml.zip | `fev_2010_xml.zip` |
| Straßenverkehrsgesetz (StVG) | https://www.gesetze-im-internet.de/stvg/xml.zip | `stvg_xml.zip` |
| Bußgeldkatalog-Verordnung (BKatV) | https://www.gesetze-im-internet.de/bkatv_2013/xml.zip | `bkatv_2013_xml.zip` |

On each page, the link labelled "XML" in the "Download" section gives this ZIP. HTML or PDF also work with
`--confirm-official`, but XML is the safest: it carries the official markers `jurabk` and `builddate`, and these
are checked automatically.

Then run:
```
python windows/tools/manual_source_import.py --all
```
Alternative: allow the host `www.gesetze-im-internet.de` in the network settings of the cloud environment. The
next session can then download the files itself.

## How it works

gesetze-im-internet.de is blocked in this environment and on the CI runners, and FeV/StVG/BKatV are not in the RIS
test phase. Put an **official** file here and import it:

```
python windows/tools/manual_source_import.py knowledge/sources/manual/fev_2010.xml --law fev_2010
python windows/tools/manual_source_import.py knowledge/sources/manual/xml.zip --law stvg --confirm-official
```

Accepted formats:
* **XML / xml.zip from gesetze-im-internet.de**: official markers are checked automatically (`<dokumente
  builddate=…>`, `<jurabk>` matching the law).
* **LegalDocML ZIP from rechtsinformationen.bund.de**: checked via the akn namespace and the ELI.
* **HTML page of gesetze-im-internet.de**: needs `--confirm-official` after you checked the page yourself.
* **PDF** (e.g. BGBl.): needs the optional `pypdf` package and `--confirm-official`.

Pipeline: parse → verify official markers → snapshot (`knowledge/sources/snapshots/<law>.json`, with provenance:
file, sha256, import time, markers) → evidence checker (every citation of that law must occur verbatim) → report
(`reports/manual_import_<law>.md`).

The knowledge base is **never changed automatically**. Rules citing the law become *verified* only when their
evidence is found verbatim in the official text. Broken citations are listed for a human to fix. A file without
official markers (and without `--confirm-official`) is stored under `unofficial/` for reference only. It is
**never** used as ground truth and never verifies anything.
