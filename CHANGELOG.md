# changelog

Format based on [Keep a Changelog](https://keepachangelog.com); versions follow [semver](https://semver.org).

## [0.1.0] - 2026-10-30

### added

- investigation plan (`design/PLAN.md`) and instructions.
- reference data catalog `data/sources/sources.json`: flight manuals, GotFriends sim manuals, EASA TCDS. `scripts/fetch_sources.py` downloads and verifies them.
- python package `msfsdiag` (src layout) with telemetry and analysis subpackages, local config (`config.local.json`), and tests.
