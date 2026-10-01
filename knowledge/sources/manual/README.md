# Manual official-source import (FeV, StVG, BKatV …)

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
