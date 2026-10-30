# msfs-diagnostics

Python SimConnect tools to record and analyze glider telemetry and performance in MSFS 2024.

The first investigation: since SU7, thermals and ridge lift seem to have no effect on gliders. These tools measure the air mass the sim reports, predict the glider's response from its published polar, and compare that with what the glider actually does. See [design/PLAN.md](design/PLAN.md).

Gliders under test: GotFriends AS 33 Me, GotFriends Discus 2C, Asobo DG1001e Neo (control).

## status

v0.3.0: recorder and per-run HTML reports work. First investigation done: no lift regression found in MSFS 2024 (store 1.9.21.0); the reported problems traced to setup (flap position, lee-side wind) and a misleading visualization. See [design/WORKLOG.md](design/WORKLOG.md) and [CHANGELOG.md](CHANGELOG.md).

## use

```
python scripts/simconnect_probe.py --out data/raw/test.jsonl --note "what you're testing"   # record (Ctrl+C to stop)
python -m msfsdiag.analysis.report --all                                                    # build reports/
```

Details: [doc/GUIDE.md](doc/GUIDE.md). Recording format: [doc/TELEMETRY.md](doc/TELEMETRY.md).

## setup

Windows, Python 3.11+, MSFS 2024.

```
python -m venv .venv
.venv\Scripts\activate
pip install -e .[dev,record]                 # record = SimConnect, for the recorder
copy config.example.json config.local.json   # then edit paths
python scripts/fetch_sources.py               # download reference manuals
pytest
```

`community_folder` in `config.local.json` is usually one of:

- MS Store: `%LOCALAPPDATA%\Packages\Microsoft.Limitless_8wekyb3d8bbwe\LocalCache\Packages\Community`
- Steam: `%APPDATA%\Microsoft Flight Simulator 2024\Packages\Community`

## layout

| path | contents |
|---|---|
| `src/msfsdiag/telemetry/` | recorder package (the recorder is `scripts/simconnect_probe.py` for now) |
| `src/msfsdiag/analysis/` | polars, derived values, steady legs, HTML reports |
| `data/` | reference manuals catalog, polars, baselines per sim build, raw recordings. See [data/README.md](data/README.md) |
| `reports/` | generated html dashboards |
| `scripts/` | one-off tools, e.g. `fetch_sources.py` |
| `design/` | [instructions](design/INSTRUCTIONS.md), [plan](design/PLAN.md), [worklog](design/WORKLOG.md) |
| `doc/` | [guide](doc/GUIDE.md), [telemetry format](doc/TELEMETRY.md) |

## contributing

Work happens in phases (see the plan): discuss, implement, test, commit. Log issues and caveats in [design/WORKLOG.md](design/WORKLOG.md) and user-facing changes in [CHANGELOG.md](CHANGELOG.md). Versions follow [semver](https://semver.org); the version lives in `src/msfsdiag/__init__.py`.

## license

MIT. Reference manuals in `data/sources/` belong to their publishers and aren't redistributed here; `fetch_sources.py` downloads them from the original hosts.
