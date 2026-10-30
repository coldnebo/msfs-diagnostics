# telemetry format

Written by `scripts/simconnect_probe.py`. Two files per run:

- `<name>.jsonl`: one JSON object per line, one line per sample (~2-3 Hz)
- `<name>.meta.json`: notes about the run

## sample fields

| key | simvar | unit |
|---|---|---|
| `t` | (wall clock) | unix seconds |
| `paused` | pause events | bool |
| `lat`, `lon` | PLANE LATITUDE / LONGITUDE | degrees |
| `alt_m` | PLANE ALTITUDE | m MSL |
| `agl_m` | PLANE ALT ABOVE GROUND | m |
| `ias_kmh`, `tas_kmh` | AIRSPEED INDICATED / TRUE | km/h |
| `vs_ms` | VERTICAL SPEED | m/s |
| `vario_ms` | VARIOMETER RATE | m/s |
| `air_w_ms` | AMBIENT WIND Y | m/s, up positive |
| `air_e_ms`, `air_n_ms` | AMBIENT WIND X / Z | m/s |
| `wind_dir`, `wind_kt` | AMBIENT WIND DIRECTION / VELOCITY | degrees (from), knots |
| `acft_wind_y_ms` | AIRCRAFT WIND Y | m/s, body axis |
| `bank_deg`, `pitch_deg`, `hdg_true` | PLANE BANK / PITCH / HEADING DEGREES TRUE | degrees |
| `weight_kg` | TOTAL WEIGHT | kg |
| `flap_idx`, `flap_l_deg` | FLAPS HANDLE INDEX, TRAILING EDGE FLAPS LEFT ANGLE | index, degrees |
| `spoilers` | SPOILERS HANDLE POSITION | percent |
| `sim_rate` | SIMULATION RATE | × |
| `on_ground` | SIM ON GROUND | 0/1 |
| `sim_local_s`, `sim_zulu_s` | LOCAL TIME / ZULU TIME | seconds since midnight (sim clock) |
| `sim_day_of_year` | LOCAL DAY OF YEAR | day |
| `sim_time_of_day` | TIME OF DAY | 0 dawn, 1 day, 2 dusk, 3 night |
| `title` | TITLE | aircraft title |

Fields added later are missing from older runs (flaps from `ridge02`, sim clock from `andes02`). Any field can be `null` for a few samples while a flight loads.

### quirks

- While paused, values freeze and `air_w_ms` reads ~0.
- The sim can also freeze without a pause event (menus, loading): position and altitude repeat exactly. The analysis treats exact repeats as frozen.
- A slew shows as IAS 0 with large vertical speeds.

## meta fields

Written at start: `tool`, `tool_version`, `started`, `sim` (`app`, `version`, `simconnect`), `aircraft_title`, `note`, `vars` (key → [simvar, unit]).

Added by hand when a run is kept: `sim.store_version`, `site`, `weather`, `mass_kg`, `segments` (see [GUIDE.md](GUIDE.md)).
