# test card: stalls and spins

The same profile in every aircraft, so the recordings compare like for like. The sim only; the real POHs prohibit some of these points.

## setup (every aircraft)

| item | setting |
|---|---|
| site | KIZA (Santa Ynez, field 674 ft), over open ground |
| entry altitude | **3,500 ft MSL** for every point (same density altitude). slew back up between points |
| weather | clear, calm, ISA (custom preset, live weather off). check on the first sample: wind < 3 kt |
| time | daytime (doesn't matter for stalls, but keep it the same) |
| load | pilot only, no rear passengers or baggage, fuel ~half. note weight and CG |
| recorder | `python -m msfsdiag.telemetry.recorder --out data/raw/<date>_stall_<aircraft>.jsonl --note "..."` |

Reference speeds per aircraft go in the session notes. If unsure, use 1.3 × the POH flaps-up stall speed as the entry speed.

## markers

- **Tap pause** before each test point and **say which point** you're flying (e.g. "A, left"). The pause separates the points in the data.
- **Landing light OFF** during the entry. Turn it **ON the moment you start recovery inputs**, OFF again once level. The light doesn't touch the flight controls, so it timestamps "recovery started" exactly.

## test points

Fly the stalls (A–D) in every aircraft before any spins.

### A. power-off stall, flaps up

1. Wings level, trimmed at the entry speed, throttle idle.
2. Hold altitude, slowing about **1 kt per second**, until the yoke is fully back.
3. Hold full aft for **3 s after the break** (or until a wing drops past 30°). Keep the ball centred with rudder, ailerons neutral.
4. Recover: landing light ON, lower the nose, full power, level the wings with rudder, climb back to level flight. Light OFF.

### B. power-off stall, full flaps

Same as A with full flaps.

### C. power-on (departure) stall, flaps up

Same as A, but at **full power**, raising the nose to stall in a climb attitude.

### D. turning stall, flaps up, 30° bank

Same as A in a steady 30° bank, power idle. Optional.

### E. spin, one turn (incipient)

1. Power idle, flaps up, entry speed, then slow down as in A.
2. At the break: **full rudder one way + full aft yoke, ailerons neutral**.
3. After **1 turn**, recover (PARE): landing light ON, power idle, ailerons neutral, **full opposite rudder**, yoke briskly forward until the rotation stops, rudder neutral, pull out without exceeding Vne or the g limit. Light OFF when level.

Fly it **left** and **right**.

### F. spin, three turns

Same as E, held for **3 turns** before recovery. Left and right.

### G. spin with aileron (optional)

Same as F with **full aileron into the spin**, then with full aileron against it. This shows how sensitive each flight model is to aileron.

## what gets measured

From the recording, per point:

| measure | from |
|---|---|
| stall warning onset (IAS, AoA) | first `stall_warn` |
| stall speed | lowest IAS before the break |
| AoA at the break | `aoa_deg` |
| pitch break, wing drop | pitch, bank, roll rate |
| height lost in recovery | entry altitude to level flight |
| spin rate | yaw rate in the developed spin (°/s, s per turn) |
| spin attitude | pitch, AoA, sideslip, roll rate |
| height lost per turn | altitude over each 360° of heading |
| turns to recover | heading change from "light ON" until rotation stops |
| pull-out | max g, max IAS |

## aircraft

| aircraft | sim title (check with `--once`) | spins in the real POH |
|---|---|---|
| Asobo C172SP Classic | `C172SP Classic …` | approved in the utility category (≤ 2,200 lb, CG limits, no rear seat or baggage) |
| WBSim C152 | ? | approved (utility category) |
| A2A Comanche 250 (PA-24) | ? | **prohibited** |

Check the real POH limits from the documents in `data/sources/` once sourced.
