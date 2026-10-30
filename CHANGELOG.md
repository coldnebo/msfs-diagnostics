# changelog

Format based on [Keep a Changelog](https://keepachangelog.com); versions follow [semver](https://semver.org).

## [0.3.0] - 2026-10-30

### added

- per-run HTML reports (`python -m msfsdiag.analysis.report`): lift vs climb vs polar prediction, track coloured by lift, steady-legs table, segment notes. self-contained and offline (vendored uPlot 1.6.30, MIT).
- `msfsdiag.analysis`: polar loading and fitting with mass, bank and altitude corrections; total-energy climb rate; steady-leg detection.
- DG-1000 20 m polar from the DG-1000S manual table; polars carry a valid speed range.
- docs: `doc/GUIDE.md`, `doc/TELEMETRY.md`.

### changed

- analysis leaves out frozen sim (exact repeats without a pause event) and airbrake use.
- `scripts/steady_segments.py` now uses `msfsdiag.analysis`.

## [0.2.0] - 2026-10-30

### added

- `scripts/simconnect_probe.py`: SimConnect recorder (JSON Lines + `.meta.json` sidecar) with air-mass, flight, flap, pause, sim-version and sim-clock fields.
- `scripts/steady_segments.py`: finds steady legs and compares reported vertical air with the total-energy climb rate.
- baseline recordings for MSFS 2024 12.2.282174.999 (AS 33 Me, DG1001e): ridge, thermal, Andes and time/live-weather tests.
- provisional AS 33 18 m / 600 kg polar points.

### findings

- no lift regression found; see `design/WORKLOG.md` (phase 1 conclusion).

## [0.1.0] - 2026-10-30

### added

- investigation plan (`design/PLAN.md`) and instructions.
- reference data catalog `data/sources/sources.json`: flight manuals, GotFriends sim manuals, EASA TCDS. `scripts/fetch_sources.py` downloads and verifies them.
- python package `msfsdiag` (src layout) with telemetry and analysis subpackages, local config (`config.local.json`), and tests.
