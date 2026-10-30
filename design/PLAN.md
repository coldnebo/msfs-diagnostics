# plan

status: draft, for discussion before phase 0 starts.

## the question

after SU7 in MSFS 2024, thermals (SSC preset) and ridge lift appear to have no effect on gliders. thermals are shown by the visualization but disappear on approach.

we want to answer, with data:

1. does the sim report rising air (vertical air mass movement) where the visualization says a thermal is, or where ridge lift should be?
2. if it does, does the glider respond to it?
3. is the result the same across all three gliders?

## hypotheses

| id | hypothesis | what we'd see |
|----|------------|---------------|
| H1 | thermals despawn or move as the aircraft approaches | vertical air near zero at the visualized position on arrival; thermal positions change over time |
| H2 | visualization and physics are decoupled | visualized thermal stays put, but vertical air at its position is near zero |
| H3 | the air mass is right, but the aircraft doesn't couple to it | vertical air positive, aircraft vertical speed shows no matching climb |
| H4 | vertical air is broken in general, not just thermals | ridge lift also missing in a controlled ridge test |
| H5 | aircraft-specific (GotFriends) | DG1001e behaves normally, GotFriends gliders don't |
| H0 | perception: lift works but is weaker or narrower than expected | small positive vertical air, consistent with the aircraft's response |
| H6 | lift parameters are MSL-based, so high terrain (Andes) squashes or removes the convective layer | lift by height differs between low and high terrain with the same preset; cutoff at a fixed MSL altitude |

status 2026-10-30 (Pennsylvania, see WORKLOG): H3 and H5 not supported. both gliders follow their polar in ridge, cloud and thermal lift. the "vanishing" visualization happens while lift is still present (display effect). H6 is the lead for the original Andes flights.

## decision tree

- vertical air at the thermal/ridge ≈ 0 → weather/lift generation problem (H1, H2, H4). aircraft is irrelevant.
- vertical air > 0, aircraft doesn't respond → flight model coupling (H3). compare aircraft for H5.
- vertical air > 0, aircraft responds as polar predicts → H0. the issue is strength or shape of lift, not a bug in coupling.

key unknown: whether SimConnect's vertical ambient wind (`AMBIENT WIND Y`) includes thermal and ridge lift at all. phase 1 settles this. if it doesn't, we fall back to inferring vertical air from the aircraft's energy balance (needs polars, phase 5) and dev mode tools.

## phases

each phase: discuss, implement, test and assess, commit, and log caveats in `design/WORKLOG.md`.

### phase 0: scaffolding (v0.1.0)

- python project (`pyproject.toml`), layout:
  - `src/msfsdiag/telemetry/`: recorder code
  - `src/msfsdiag/analysis/`: dashboard generator code
  - `data/`: see [data/README.md](../data/README.md)
    - `data/sources/`: reference manuals and TCDS, cataloged in `sources.json` (PDFs gitignored, fetched by `scripts/fetch_sources.py`)
    - `data/polars/`: polar json with source citations
    - `data/baselines/msfs2024-<build>/<aircraft-id>/`: measured results per sim build
    - `data/raw/`: recordings (gitignored, except small reference captures)
  - `reports/`: generated dashboards
- local config json for paths (e.g. Community folder), gitignored, with a committed example.
- `README.md`, `CHANGELOG.md`.

note: this layout replaces the top-level `telemetry/` and `analysis/` folders from the initial commit, to keep code and data apart.

### phase 1: SimConnect spike

goal: prove we can read what we need from MSFS 2024, and answer the key unknown.

- connect from python, sample at a fixed period (target 10–20 Hz).
- read: position, altitude, attitude, IAS/TAS, vertical speed, ambient wind X/Y/Z, total weight, sim rate, pause state, aircraft title.
- check whether GotFriends gliders expose useful L: vars (e.g. vario, total energy).
- test: in a known ridge-lift setup, does `AMBIENT WIND Y` go positive?

### phase 2: recorder v1 and format

- recorder CLI: start/stop, auto-named files (`<tool version>_<UTC datetime>_<aircraft>.jsonl`).
- format: JSON Lines samples + a metadata json (sim version, aircraft and version, weight/ballast, preset name, location, tool version, notes).
- `doc/TELEMETRY.md`.

### phase 3: controlled test flights

test protocol, written up in `doc/GUIDE.md`:

- **ridge test** (deterministic, most repeatable): Bald Eagle Mountain, PA, from Ridge Soaring Gliderport (FAA 79N). the ridge runs roughly SW–NE with its steep face to the NW (verify the axis on the in-sim map).
  - weather: custom preset, live weather off, clear sky, thermals off, wind constant with altitude.
  - track: from 79N, ~300 ft above the crest on the NW (windward) side, fly NE along the ridge 10–15 km at constant IAS, then return on the same line.
  - runs: wind 315° / 20 kt (onto the face, lift expected); wind 045° / 20 kt (along the ridge, control, little or no lift); calm (control, also a still-air polar check).
  - 3 runs per glider per wind case.
- **thermal test**: SSC preset (Soaring Weather v5.0.2), visualization on, fixed location and time. note the visualized thermal's position, fly straight through it, then circle at fixed bank. screen recording with sim time visible, to line up with telemetry.
- **still-air test**: calm preset, fixed speeds, for later polar comparison.
- each test in all three gliders, at least three runs each.

### phase 4: analysis dashboard v1

single html file, no server (data embedded at generation time, or loaded by drag-and-drop):

- timeline: vertical air vs aircraft vertical speed.
- map/track colored by vertical air, with visualized thermal positions marked by hand.
- per-run summary and cross-aircraft comparison.

this phase should answer questions 1–3 for the big symptom.

### phase 5: polars and prediction

- polars from flight manuals to json, with corrections for weight/ballast, bank angle, flaps, IAS→TAS. sources are in `data/sources/sources.json`; the polars are graphs, so they must be digitized (cross-check against the min sink / best glide tables where the manual has them).
- digitized points are read once and frozen in `data/polars/*.json`, citing source id and page. analysis fits curves from those points only, never re-reads the chart. changing a point is a deliberate, logged edit.
- three references per glider where available: real manual, sim developer's manual (intended polar), and the measured still-air baseline.
- compare manual polar to the still-air recordings (flight model fidelity, a separate question).
- predicted vs actual vertical speed given measured air mass.

### phase 6: findings report

- write-up with dashboards and raw data, suitable for an Asobo / GotFriends bug report.

## needed from the user

- **dev mode research** (most useful now): is there a weather/thermal debug view that lists thermal positions and strength? does it agree with the visualization? any SDK documentation of thermal simvars in 2024?
- **SSC preset**: [Soaring Weather](https://flightsim.to/addon/56827/soaring-weather) v5.0.2. still needed: which preset(s) within it you use.
- **ridge**: chosen, Bald Eagle Mountain / 79N (see phase 3).
- **flight manuals**: found and cataloged in `data/sources/`. two are proxies; the originals aren't publicly hosted:
  - AS 33 Me manual (Schleicher, 01.11.2022). using the AS 33 Es manual meanwhile.
  - DG-1001E manual (DG Aviation, Dec 2022). using the DG-1000S manual meanwhile.

## notes

- the GotFriends gliders credit "custom physics" in their manuals, so they may handle lift differently from the stock sim. this makes the Asobo DG1001e important as the control (H5).
- we report deltas from predicted behavior, not root causes. the decision tree says where a delta comes from (air mass vs aircraft response), which is as far as we go.
