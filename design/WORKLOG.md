# worklog

issues and caveats found while carrying out the plan. newest first.

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
