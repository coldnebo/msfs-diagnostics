"""Load a recording and derive per-sample values for analysis.

A sample is usable ("ok") when it has the core fields, the sim isn't paused,
and it isn't a slew or reposition (IAS under 40 km/h in the air, or a vertical
speed no glider can fly).

Derived per sample:
- te_ms: total-energy climb rate, d(alt + TAS²/2g)/dt over a centred window.
  speed traded for height (or back) doesn't count as climb or sink.
- pred_sink_ms: polar sink for this IAS, mass, bank and TAS
- pred_climb_ms: air_w_ms − pred_sink_ms, what the glider should climb at
"""

import gzip
import json
from dataclasses import dataclass, field
from pathlib import Path

from .polar import for_title

G = 9.81
CORE = ("lat", "lon", "alt_m", "agl_m", "ias_kmh", "tas_kmh", "vs_ms", "air_w_ms", "bank_deg", "weight_kg")
SLEW_VS_MS = 25.0


@dataclass
class Run:
    path: Path
    meta: dict
    rows: list
    polars_used: dict = field(default_factory=dict)  # title -> polar name, or None


def load(path, polars=(), te_window_s=2.5) -> Run:
    path = Path(path)
    opener = gzip.open if path.name.endswith(".gz") else open
    with opener(path, "rt", encoding="utf-8") as f:
        rows = [json.loads(line) for line in f if line.strip()]
    meta_path = path.with_name(path.name.removesuffix(".gz").removesuffix(".jsonl") + ".meta.json")
    meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}

    prev = None
    for r in rows:
        complete = all(isinstance(r.get(k), (int, float)) for k in CORE)
        slew = complete and (r["ias_kmh"] < 40 and not r.get("on_ground") or abs(r["vs_ms"]) > SLEW_VS_MS)
        # frozen: the sim stopped (menus, loading) without reporting a pause.
        # flying samples never repeat position and altitude exactly.
        frozen = complete and prev is not None and all(r[k] == prev.get(k) for k in ("lat", "lon", "alt_m"))
        r["ok"] = complete and not r.get("paused") and not slew and not frozen
        r["slew"] = bool(slew)
        r["frozen"] = bool(frozen)
        # airbrakes out: the energy loss is real, but the polar doesn't apply
        r["brakes"] = (r.get("spoilers") or 0) > 1
        prev = r

    _total_energy_rate(rows, te_window_s)

    run = Run(path, meta, rows)
    for r in rows:
        title = r.get("title")
        if title not in run.polars_used:
            p = for_title(polars, title)
            run.polars_used[title] = p
        p = run.polars_used[title]
        if r["ok"] and p and not r["brakes"]:
            s = p.sink(r["ias_kmh"], r["weight_kg"], r["bank_deg"], r["tas_kmh"])
            r["pred_sink_ms"] = s
            r["pred_climb_ms"] = None if s is None else r["air_w_ms"] - s
        else:
            r["pred_sink_ms"] = r["pred_climb_ms"] = None
    run.polars_used = {t: (p.name if p else None) for t, p in run.polars_used.items()}
    return run


def find_runs(directory):
    """Recordings under a directory: *.jsonl and *.jsonl.gz."""
    d = Path(directory)
    return sorted([*d.rglob("*.jsonl"), *d.rglob("*.jsonl.gz")])


def peek_title(path):
    """Aircraft title of a run without loading it: from the .meta.json, else the first sample."""
    path = Path(path)
    meta_path = path.with_name(path.name.removesuffix(".gz").removesuffix(".jsonl") + ".meta.json")
    if meta_path.exists():
        title = json.loads(meta_path.read_text(encoding="utf-8")).get("aircraft_title")
        if title:
            return title
    opener = gzip.open if path.name.endswith(".gz") else open
    with opener(path, "rt", encoding="utf-8") as f:
        return json.loads(f.readline()).get("title", "")


def glider_runs(directory, polars):
    """Runs whose aircraft has a polar (the glider analysis skips the others)."""
    return [p for p in find_runs(directory) if for_title(polars, peek_title(p))]


def _energy_height(r):
    v = r["tas_kmh"] / 3.6
    return r["alt_m"] + v * v / (2 * G)


def _total_energy_rate(rows, half_window_s):
    """Centred difference of energy height over ±half_window, within runs of ok samples."""
    i = 0
    n = len(rows)
    while i < n:
        if not rows[i]["ok"]:
            rows[i]["te_ms"] = None
            i += 1
            continue
        j = i
        while j < n and rows[j]["ok"]:
            j += 1
        block = rows[i:j]
        lo = hi = 0
        for k, r in enumerate(block):
            t = r["t"]
            while block[lo]["t"] < t - half_window_s:
                lo += 1
            while hi + 1 < len(block) and block[hi + 1]["t"] <= t + half_window_s:
                hi += 1
            a, b = block[lo], block[hi]
            dt = b["t"] - a["t"]
            r["te_ms"] = (_energy_height(b) - _energy_height(a)) / dt if dt > 0.5 else None
        i = j
