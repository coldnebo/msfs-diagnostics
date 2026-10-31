# guide

How to record a flight and look at it. Setup is in the [README](../README.md).

## record

Start MSFS 2024 and get into the aircraft, then:

```
python scripts/simconnect_probe.py --out data/raw/<date>_<name>.jsonl --note "site, preset, what you're testing"
```

- It prints a line every half second and writes every sample (about 2–3 per second) to the `.jsonl` file, plus a `.meta.json` notes file with the sim version and your note.
- Stop with Ctrl+C. Samples are written as they arrive, so nothing is lost if the process is killed.
- It keeps recording across pauses, aircraft changes and flight loads.
- `--once` prints one sample with every field and exits: a quick connection check.

### marking moments

Tap pause (pause, unpause) to mark a moment, e.g. "the visualization vanished here". Pauses are recorded and show as grey bands in the report.

### flying for clean data

- Steady legs: hold airspeed (±5 km/h) and keep wings level for at least 15–30 s. These become rows in the report's steady-legs table.
- Use the flap setting the flight manual gives for your speed. A wrong flap (e.g. landing flap at 170 km/h) shows up as ~1 m/s of extra sink.
- Airbrakes, slews and repositioning are detected and left out of the comparison.

### keeping a run

Move runs you want to keep from `data/raw/` (gitignored) to
`data/baselines/msfs2024-<build>/<aircraft>/runs/`, and add to the `.meta.json`:

- `site`, `weather`, `mass_kg`
- `segments`: a list of `{"from": "HH:MM:SS", "to": "HH:MM:SS" | "end", "weather": ..., "what": ...}` in local wall-clock time. These label the report's timeline.

The build string is in the `.meta.json` (`sim.version`, read from SimConnect). Add the store version (`sim.store_version`) by hand.

## report

```
python -m msfsdiag.analysis.report data/baselines/.../run.jsonl   # one run
python -m msfsdiag.analysis.report --all                           # every baseline + reports/index.html
```

Reports land in `reports/` (gitignored), mirroring the baselines folders. Each is a single HTML file with its data and chart library built in: open it from disk, no server or internet needed.

What's on the page:

- **Lift vs climb**: air = vertical air reported by the sim (`AMBIENT WIND Y`); climb = the glider's total-energy climb rate (altitude plus speed, so pull-ups and dives don't count); predicted = air − polar sink. If the glider uses lift as it should, climb and predicted overlap. Drag to zoom; the two charts and the track follow.
- **Bands**: grey = paused or frozen, amber = slew, red = airbrakes; light blue = the run's segments from `.meta.json`.
- **Track**: coloured by vertical air (blue sink, red lift). It shows the part of the flight in view and, when that spans two sites, the busier one. The dot follows the cursor.
- **Steady legs**: per leg, sink relative to the air (air − climb) next to the polar's prediction. Δ = measured − predicted; positive means the glider did worse than its polar. Click a row to zoom to it.

Same table as text: `python scripts/steady_segments.py <run.jsonl>`.

### polars page

`reports/polars.html` (built by `--all`) puts every steady leg from every baseline against the manual polars:

- **All aircraft**: predicted vs measured sink. On the dashed line the glider does exactly what its polar says; the strip is ±0.15 m/s.
- **Per aircraft**: the polar curve with each leg scaled to the polar's reference mass, straight flight and sea level, plus the gap per leg. Dots are coloured by flap setting. The stats give the median gap and its spread: a steady offset with small spread means the polar is a little off for this airframe, while scatter, or dots far above the curve, means something in the flight (flaps, technique) or the sim differs.

## stalls and spins

Fly the points on [TESTCARD-stall-spin.md](TESTCARD-stall-spin.md) with the high-rate recorder (`--out ....jsonl.gz`). Afterwards, list each point in the run's `.meta.json` `segments` with a `point` (A, B, C, E, F, G; `-` to skip) and a `what`, then:

```
python -m msfsdiag.analysis.stallspin_report
```

For each stall-spin run this writes `results/<run>.points.json` next to `runs/` (small, committed) and a page per aircraft, plus `reports/stall-spin.html` comparing them. Per point it detects the stall warning, yoke full aft, peak AoA, departure, pro-spin rudder, yoke forward, opposite rudder, rotation stop and level-off, and measures:

- **stall**: warning IAS and AoA, peak AoA, pitch break, wing drop, height lost
- **spin**: direction, turns (total, before the first recovery input, after it, after opposite rudder), what stopped it, per-turn seconds and feet, and the developed spin (after turn 1): s/turn, ft/turn, AoA, pitch, IAS trend, sideslip. Mode: **flat** (mean AoA ≥ 35°), **spiral-like** (IAS climbing > 0.8 kt/s with AoA < 22°) or **steep**.

Turns are counted about the vertical axis from the body rates, so they stay right when the nose is near vertical. Inside a flat spin the indicated airspeed is meaningless.

## polars

`data/polars/*.json`, one per aircraft, matched to the sim's aircraft title by `match_titles`. See [data/README.md](../data/README.md) and the module docstring in `src/msfsdiag/analysis/polar.py` for the format and corrections (mass, bank, altitude). Points read from a chart are recorded once and reused; changing them is a deliberate, logged edit.
