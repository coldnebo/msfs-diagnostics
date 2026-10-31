# changelog

Format based on [Keep a Changelog](https://keepachangelog.com); versions follow [semver](https://semver.org).

## [0.8.0] - 2026-10-31

### added

- 3D view per stall/spin run (`msfsdiag.analysis.stallspin_3d`): recorded path at true scale with an aircraft flown along it at the recorded pitch, bank and heading; point picker, play/pause, speed, scrubber, follow camera, live readout; URL `#p=<point>&t=<s>` keeps the moment. three.js r147 + OrbitControls (MIT) vendored, so pages work offline.
- aircraft pages link their 3D view; examples include the three 3D pages, with a landing card opening the Comanche mid-spin.
- heading in the normalised stall/spin samples.

### changed

- example screenshots use software WebGL and support URL fragments.

## [0.7.2] - 2026-10-31

### changed

- examples landing page: sections per project, a preview thumbnail for every page (`examples/img/thumb/`, 16:10 at half scale, ~40 KB each), links to every doc on GitHub.
- `build_examples.py --screenshots` waits for Edge to finish writing each PNG.

## [0.7.1] - 2026-10-31

### added

- examples: stall/spin comparison and per-aircraft pages, screenshots, README sections (rebuilding them needs the local recordings; without them the build keeps the existing pages).

## [0.7.0] - 2026-10-31

### added

- stall/spin analysis (`msfsdiag.analysis.stallspin`): per test point, event detection (warning, full aft, peak AoA, departure, pro-spin rudder, yoke forward, opposite rudder, stop, level) and measurements (stall: warning, peak AoA, pitch break, wing drop; spin: direction, turns before/after recovery inputs, what stopped it, per-turn time and height, developed-spin rate, AoA, IAS trend, mode flat/spiral-like/steep).
- `python -m msfsdiag.analysis.stallspin_report`: committed `results/*.points.json`, per-aircraft pages (charts with event markers, thinned to 20 Hz), and `reports/stall-spin.html` comparing the aircraft.
- results for the 2026-10-31 session (C172, C152, Comanche).

## [0.6.0] - 2026-10-31

### added

- `msfsdiag.telemetry.recorder`: high-rate recorder (one data definition every sim frame, ~60 Hz) with stall/spin fields (AoA, sideslip, body rates, g, stall warning, control inputs and surfaces, engine, CG, gear, light markers); `--out *.jsonl.gz` writes gzip; values rounded.
- stall/spin project: test card `doc/TESTCARD-stall-spin.md`, plan `design/stall-spin/PLAN.md`, first session notes for the C172, C152 and Comanche (recordings local only).
- analysis reads `.jsonl.gz`; glider reports skip runs whose aircraft has no polar.

## [0.5.0] - 2026-10-30

### added

- `examples/`: showcase reports from the first investigation (polars page, four runs), an index, screenshots and a guide to reading them. rebuilt by `scripts/build_examples.py --screenshots`.
- `AGENTS.md` (with `CLAUDE.md` importing it): commands, rules, live-session workflow and gotchas for AI agents.
- README rewritten around the technique, findings and how to adapt it to other gliders or sims; polar file format in `data/README.md`.

### changed

- reports embed uPlot's MIT notice.

## [0.4.0] - 2026-10-30

### added

- polar comparison page `reports/polars.html` (built by `report --all`, or `python -m msfsdiag.analysis.polar_report`): per aircraft, the manual polar with every steady leg scaled to it, the gap per leg, and summary stats; across aircraft, predicted vs measured sink. inline SVG with hover details and a full table.
- polars can name flap indices (`flap_index_names`) and say they have no flaps (`flaps: false`).

### changed

- run reports: airspeed and height are now two single-axis charts instead of one dual-axis chart.

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
