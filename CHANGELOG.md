# changelog

Format based on [Keep a Changelog](https://keepachangelog.com); versions follow [semver](https://semver.org).

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
