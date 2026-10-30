# worklog

issues and caveats found while carrying out the plan. newest first.

## 2026-10-30: phase 1 conclusion

**summary: no lift regression found in MSFS 2024 (store 1.9.21.0 / SimConnect 12.2.282174.999). the problems reported after SU7 trace to setup, plus a misleading visualization.**

- **live weather (India, real-world ~01:15)**: Live weather with the sim clock still at noon gave +0.1 to +0.3 m/s; Live + real time (sim 01:16, night) gave 0 to +0.35. applying SSC 169 on top reset the sim clock to 12:05 and the wind to the preset's, and lift came back within a minute (to +2 m/s and building). **an SSC preset fully replaces Live weather and real time; nothing carried over.** with Live weather, expect real-world conditions, including no convection at night.
- **gliders**: GotFriends AS 33 Me and Asobo DG1001e matched their polars (to ~0.1-0.2 m/s) in ridge, cumulus and thermal lift, in Pennsylvania, Peru and India.
- **causes found**: (1) AS 33 flap at index 6 (landing range) at high speed cost ~1 m/s; (2) Andes flights used a W wind on a slope flown from its lee side: sinking air instead of ridge lift.
- **visualization**: the thermal visualization disappears while lift is still present, and the dev Atmospheric Turbulence overlay shows max colour over still air. neither is a reliable lift map.
- **not tested**: MSL cloud base over terrain above ~1,800 m (H6); AS 33 Me in thermals; GotFriends Discus 2C at all.

## 2026-10-30: phase 1 spike, Andes (SPJE) and time-of-day tests

recordings: `data/raw/2026-10-30_andes01_spje.jsonl` (SSC 185 → 169), `..._andes02_spje.jsonl` (sim clock fields added; ends in India). DG-1001-E Neo, 671 kg.

- **original Andes flights**: near SPJE (Jaén, Peru), SSC 187 with W wind, applied on top of Live weather, flown at real-world night, low along a slope heading south.
- **valley cumulus, SSC 185 (Low Cu T10-14 W5)**: ~1,000 m AGL (1,630-1,775 m MSL, ground 640-760 m): lift built to +2.9 m/s; 153 s leg, sink relative to air 0.50 vs ~0.6.
- **lee side confirmed**: same slope (ground 1,050-1,390 m), 120-400 m AGL. W wind (SSC 185): −0.4 to −1.4 m/s (sinking air). E wind (SSC 169, Low Cu T10-14 E5): +0.5 to +2.1 m/s, DG held or gained height at ~100 km/h. the W sample is short (~20 s, right after a dive). **the original "no lift, very low" is explained by flying the lee side of the slope.**
- **sim clock vs real clock**: India 24.06 N 72.21 E, sim local 12:15 (day 301), real local ~01:10. lift up to +4.05 m/s (panel: clouds 17%), straight core leg 38 s at 90 km/h: air +3.61, TE climb +3.04, sink relative to air 0.57. **real-world night does not suppress lift when a preset sets the sim time.**
- **dev overlay ≠ lift map**: in India the Atmospheric Turbulence overlay showed max-colour (purple) streaks almost everywhere while the panel read 0% on all sources and `AMBIENT WIND Y` ≈ 0.
- **recorder**: survives loading a new flight; fields read null for a few samples during the load.
- **untested**: Live-weather carry-over under an SSC preset (original setup); MSL cloud base over terrain above ~1,800 m (H6).

## 2026-10-30: phase 1 spike, default-weather thermals, and the Andes lead

- **default Clear preset, Oct 30 noon**: weak thermal, reported lift up to ~+0.5 m/s for ~20 s. the panel attributed 4-6% of turbulence to thermals.
- **default Clear preset, June 21 noon**: 88 s circling at 98 km/h, 26° bank: reported lift +1.37 m/s, total-energy climb +0.82, sink relative to air 0.55 vs 0.73 predicted (DG-1000S 0.62 × cos^-1.5 bank). panel attributed it to thermals.
- **visualization vanishing ≠ lift vanishing**: on the SSC 093 cloud-lift climb, the thermal visualization disappeared while the vario (and `AMBIENT WIND Y`, ~+3 m/s) showed lift. the "thermal disappears as I approach" symptom looks like a display effect (visualization hidden near or inside the thermal), not missing lift.
- **the in-game thermal visualization panel gives a finer breakdown of the lift source** than the dev turbulence panel. per the pilot, it lines up with what we measured.
- **original problem flights were in the Andes, flying low.** hypothesis H6: some lift parameters (e.g. SSC cloud base "6,000 ft", thermal top) are set relative to MSL, so over high terrain (ground 3,000 m+) the convective layer is squashed or underground and thermals barely form. next test: same preset and glider in the Andes, lift-by-height profile, compared with Pennsylvania in both AGL and MSL.

## 2026-10-30: phase 1 spike, DG1001e ridge + first thermal tests

sim: MSFS 2024 store version 1.9.21.0; SimConnect reports app "SunRise" 12.2.282174.999. aircraft: Asobo DG-1001-E Neo, 748 kg (full ballast), no flaps. recording `data/raw/2026-10-30_run03.jsonl` (also contains the end of an AS 33 session and the aircraft switch).

- **site**: the DG flew a different ridge, ~125 km east of 79N (40.82 N, 76.54 W), and the thermal tests nearby.
- **DG ridge (SSC 368, NW15)**: steady legs at ~100 km/h: sink relative to air 0.45-0.55 m/s vs 0.62 in the DG-1000S table (20 m, ~43 kg/m², 98 km/h). slightly better than the proxy manual; plausible for the neo winglets.
- **thermals (SSC 093, Low Cu T4-8 NW5, cloud base ~6,000 ft)**:
  - pass 1, straight at 100 km/h, 300-430 m AGL, pause markers: the visualized thermal vanished ~1.0 km before the point judged to be its centre. reported lift peaked at +0.9 m/s near where the visualization vanished; ~0 at the judged centre. dev-mode turbulence panel: thermals ≤3%. the DG followed the reported air correctly.
  - pass 2, ~900 m AGL: straight entry built from 0 to +3.2 m/s over ~800 m; circling at 20-30° bank climbed +1.8 m/s vs +1.8 predicted (2.5 air − ~0.7 circling sink).
  - pass 3, same thermal from 250 m AGL (after slew) to ~900 m AGL, 277 s: mean reported lift +2.77, total-energy climb +2.17, sink relative to air 0.59 vs 0.6. lift by AGL: 200-299 m +1.7, 300-399 +2.9, 400-599 +3.3, 700-899 +2.5-3.0, max +3.9.
- **lift source not established**: the dev-mode panel "Turbulence → currently caused by" (Clouds / Terrain / Wake / Thermals %, with EDR per axis) attributes *turbulence*, not the mean updraft. it showed Clouds 2-3%, Thermals 0-3% during these passes. so it doesn't say whether the +3 m/s was a thermal or a cloud updraft. corrects an earlier note in this entry that called it "cloud lift".
- **the dev overlay used for pass 1 was "Atmospheric Turbulence"** (colour scale min→max: cyan→green→orange→red→purple), with CFD and Wake off. a "red" patch is high turbulence or airflow, not necessarily a thermal. still to confirm which visualization showed the original SU7 symptom (in-game thermal visualization vs this dev overlay).
- **conclusion so far**: whenever SimConnect reports lift, both gliders (GotFriends AS 33 Me, Asobo DG) climb by it minus their own polar sink, to ~0.1 m/s. no sign of aircraft ignoring lift. thermal strength matches T4-8 (2-4 m/s) when found.
- **open question**: whether the thermal visualization matches the air. pass 1 shows a ~1 km mismatch; needs repeats with positions.
- **height hypothesis dropped**: pass 1's weak lift was not a height effect; pass 3 had ~+3 m/s from 300 m AGL.
- **`AMBIENT WIND Y` reads ~0 while paused**; paused samples are excluded.

## 2026-10-30: phase 1 spike, first ridge test (AS 33 Me)

setup: Bald Eagle Mountain from 79N, SSC 368 (Overcast T0 NW15, Soaring Weather v5.0.2), GotFriends AS 33 Me 18 m, 599 kg (full ballast). recordings: `data/raw/2026-10-30_ridge01_as33me.jsonl`, `..._ridge02_...` (local only). tools: `scripts/simconnect_probe.py`, `scripts/steady_segments.py`.

- **SimConnect works with MSFS 2024** using the PyPI `SimConnect` package (0.4.26, its bundled DLL) on Python 3.14. no SDK DLL needed so far.
- **rate is ~3 Hz**: the package makes one request per variable. fine for ridge work; the phase 2 recorder needs one batched data definition.
- **`AMBIENT WIND Y` reports ridge lift**: +1.9 to +3 m/s on the windward face at ~150-250 m AGL, ~+1.3 m/s at ~370 m AGL, −0.4 to −1 m/s on the lee side. near zero before the wind built. `AIRCRAFT WIND Y` agrees with it to within a few tenths.
- **the AS 33 Me responds to ridge lift as the polar predicts, with the right flap.** steady legs at ~110 km/h, flap N (index 4): sink relative to air 0.56-0.72 m/s vs ~0.6 on the chart, in lift, weak air and lee sink alike.
- **wrong flap explains the "missing lift"**: at 173 km/h with flap index 6 (25°, landing range), sink relative to air was ~1.95 m/s vs ~1.0 expected with flap 2. the first legs looked like the glider was getting only half the lift; it wasn't.
- **flap mapping (GotFriends AS 33)**: `FLAPS HANDLE INDEX` 4 = N. index 6 reads 25° on `TRAILING EDGE FLAPS LEFT ANGLE`. full mapping still to confirm.
- **total-energy correction needed**: speed changes during a leg shift the raw vertical speed by up to ~0.4 m/s. `steady_segments.py` now uses altitude + kinetic energy.
- **pause shows up as frozen values**, and a slew/reposition as IAS 0 with a large VS spike. the recorder should flag both.
- **SSC panel**: T0 (no thermals) is only offered with Overcast, and 20 kt wasn't available there; used NW 15 kt. sim-reported wind on the ridge was 310-316° / 13-15 kt.
- **transient at unpause**: right after unpausing, wind briefly read 130°/10 kt with −3.3 m/s vertical air, then returned to normal within seconds.
- polar points used are provisional, read by eye: `data/polars/as33-18m_600kg_provisional.json`.

## 2026-10-30: phase 0 (scaffolding)

- **manuals not public**: the real AS 33 Me (Schleicher, 01.11.2022) and DG-1001E (DG Aviation, Dec 2022) flight manuals aren't hosted publicly. proxies are the AS 33 Es and DG-1000S manuals; see `fit` in `data/sources/sources.json`.
- **AS 33 Es polars are preliminary**: the manual marks them "Data basis: Preliminary estimate", and the circling polar is "not yet available".
- **polars are graphs**: all three manuals give polars as charts (the AS 33 Es is a scan). they'll be digitized once and frozen, per the instructions. the Discus and DG manuals have min sink / best glide tables to cross-check.
- **Discus manual is German only** (Flughandbuch, Jan 2016 rev 1). numbers and charts don't need translation.
- **PDFs not committed**: they're copyrighted and the repo is public. the catalog keeps sha256 checksums, so a changed upstream file is detected.
- **GotFriends custom physics**: both GotFriends sim manuals credit "custom physics". the Asobo DG1001e is the control.
- **python**: developed on Python 3.14; `requires-python` is 3.11+. SimConnect library compatibility with 3.14 is checked in phase 1.
