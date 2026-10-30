# AGENTS.md

Guidance for AI agents working in this repo. Humans: see [README.md](README.md) and [doc/GUIDE.md](doc/GUIDE.md).

## what this is

Tools to check whether a glider sim's lift reaches the glider. A recorder samples MSFS 2024 over SimConnect. The analysis compares:

- the sim's reported vertical air (`AMBIENT WIND Y`)
- the glider's total-energy climb rate
- a prediction from the glider's published polar

Status and findings so far: top of [design/WORKLOG.md](design/WORKLOG.md). Plan and hypotheses: [design/PLAN.md](design/PLAN.md). Original brief: [design/INSTRUCTIONS.md](design/INSTRUCTIONS.md).

## commands

Windows; the venv is `.venv` (use `.venv/Scripts/python` from Git Bash).

```
pip install -e .[dev,record]                          # record = SimConnect (recorder only)
pytest                                                # all tests; keep them passing
python scripts/simconnect_probe.py --once             # one sample from the running sim, all fields
python scripts/simconnect_probe.py --out data/raw/<date>_<name>.jsonl --note "..."   # record
python -m msfsdiag.analysis.report --all              # reports/ (gitignored): one page per baseline run + polars.html + index.html
python scripts/steady_segments.py <run.jsonl>         # steady legs as text
python scripts/build_examples.py --screenshots        # examples/ (committed); screenshots need Microsoft Edge
python scripts/fetch_sources.py                       # download reference manuals (PDFs are gitignored)
```

## layout

- `src/msfsdiag/analysis/`
  - `polar.py`: fit and corrections; `to_reference` undoes them
  - `run.py`: load a recording, flag unusable samples, total-energy rate, predictions
  - `legs.py`: steady legs
  - `report.py`: per-run HTML
  - `polar_report.py`: polars page
  - `vendor/`: uPlot, MIT
- `scripts/`: recorder (`simconnect_probe.py`), text view, example builder, manual fetcher
- `data/polars/*.json`: one polar per aircraft, matched to the sim's `TITLE` by `match_titles`
- `data/baselines/msfs2024-<build>/<aircraft>/runs/`: kept recordings (`.jsonl` + `.meta.json`)
- `data/raw/`: scratch recordings (gitignored)
- `data/sources/sources.json`: catalog of manuals and type certificates (PDFs gitignored)

## rules

- **Work in phases**: discuss, implement, test, commit. Record caveats and findings in `design/WORKLOG.md` (newest first) and user-facing changes in `CHANGELOG.md`. Bump `src/msfsdiag/__init__.py` (semver) and tag `vX.Y.Z` (annotated) at milestones.
- **Never push, open PRs or post anywhere without the user asking.**
- **Recordings are evidence: don't edit `.jsonl` files.** Put corrections and context in the `.meta.json` (`note`, `site`, `weather`, `mass_kg`, `segments`).
- **Polar points read from a chart are frozen.** Analysis uses only the stored points. Changing one is a deliberate edit, logged in the worklog. Prefer a manual's table over its chart. Mark proxies and provisional data (`status`, `fit`).
- **Don't commit copyrighted PDFs.** Catalog them in `sources.json` with URL and sha256.
- **Report deltas, not causes.** Say what the data shows (air, climb, gap) and where it breaks down. Don't claim a root cause the data can't separate.
- **Rebuild `examples/` with the script after analysis changes**, and look at the screenshots before committing.

## running a live session with a pilot

The sim usually runs on the same machine, so you can read it directly.

1. `--once` to confirm the connection, aircraft and sim version.
2. Start the recorder in the background with `--out data/raw/...` and a `--note`. It survives pauses, aircraft changes and flight loads, but restart it to pick up new fields.
3. Ask for one change at a time and note the wall-clock time of each (preset applied, flap moved, aircraft switched). These become `segments` in the meta.
4. Have the pilot **tap pause to mark moments** ("the visualization vanished"). Pause transitions are in the data (`paused`).
5. For clean legs: steady IAS (±5 km/h), wings level, 30–60 s, the right flap for the speed. Ask what preset and flap they're using; check the sim's own values (`flap_idx`, `wind_*`, `sim_local_s`) rather than assuming.
6. Analyze from the file with `run.load` + `legs.find_legs` (or `steady_segments.py --since <unix t>`). Report the numbers and what they mean in a short table.
7. Afterwards, move the run to `data/baselines/msfs2024-<build>/<aircraft>/runs/`, write the meta (segments in local `HH:MM:SS`), and rebuild reports.

## gotchas

### the data

- **Paused**: values freeze and `AMBIENT WIND Y` reads ~0. Excluded.
- **Frozen without a pause event** (menus, loading): position and altitude repeat exactly. `run.py` flags exact repeats.
- **Slew or reposition**: IAS 0 and huge vertical speeds. Excluded.
- **Airbrakes** (`spoilers` > 1%): real energy loss, but the polar doesn't apply. Excluded from predictions and legs; shown as a band.
- **Use the total-energy climb, not `VERTICAL SPEED`.** Speed changes alone move VS by ±5 m/s.
- **Flaps matter**: a wrong flap at speed costs ~1 m/s and looks exactly like missing lift.
  - GotFriends AS 33: `FLAPS HANDLE INDEX` 4 = N; 6 reads 25° (landing range). Other indices are unmapped.
  - Each flap position only matches the polar in its own speed band.
- **The DG polar is a parabola from two table points**, valid 70–130 km/h only.
- **The recorder runs at ~2–3 Hz** (the PyPI `SimConnect` package makes one request per variable). Fine for legs, not for gusts.

### the sim

- **Versions**: SimConnect reports app `SunRise` and a build like `12.2.282174.999`. The store version (e.g. 1.9.21.0) isn't available over SimConnect; ask the user.
- **SSC (Soaring Weather) presets set the sim clock and override Live weather** completely. Live weather follows the real atmosphere, so at real-world night there's almost no convection, whatever the sim clock says.
- **Dev mode's "Turbulence → currently caused by" panel attributes turbulence (EDR), not lift.** The Atmospheric Turbulence overlay isn't a lift map, and the thermal visualization disappears near or inside a thermal while the lift remains.
- **Wind direction vs slope side**: a slope on the lee side gives sinking air. Check which side the pilot is on.

### the environment

- **`python -I`** ignores `PYTHONIOENCODING`. Call `sys.stdout.reconfigure(encoding="utf-8")` when printing non-ASCII on Windows.
- **Windows can't convert timestamps near 1970 to local time.** Tests use realistic times.
- **No Node**: render and screenshot pages with headless Edge (`--headless=new --screenshot=... --virtual-time-budget=3000`).
