# worklog

issues and caveats found while carrying out the plan. newest first.

## 2026-10-30: phase 0 (scaffolding)

- **manuals not public**: the real AS 33 Me (Schleicher, 01.11.2022) and DG-1001E (DG Aviation, Dec 2022) flight manuals aren't hosted publicly. proxies are the AS 33 Es and DG-1000S manuals; see `fit` in `data/sources/sources.json`.
- **AS 33 Es polars are preliminary**: the manual marks them "Data basis: Preliminary estimate", and the circling polar is "not yet available".
- **polars are graphs**: all three manuals give polars as charts (the AS 33 Es is a scan). they'll be digitized once and frozen, per the instructions. the Discus and DG manuals have min sink / best glide tables to cross-check.
- **Discus manual is German only** (Flughandbuch, Jan 2016 rev 1). numbers and charts don't need translation.
- **PDFs not committed**: they're copyrighted and the repo is public. the catalog keeps sha256 checksums, so a changed upstream file is detected.
- **GotFriends custom physics**: both GotFriends sim manuals credit "custom physics". the Asobo DG1001e is the control.
- **python**: developed on Python 3.14; `requires-python` is 3.11+. SimConnect library compatibility with 3.14 is checked in phase 1.
