"""Steady legs: stretches of usable samples where bank and IAS hold steady.

For each leg, the glider's sink relative to the air is
    air_w (mean) − total-energy climb rate (from the leg's end points)
and is compared with the mean polar prediction over the leg.
"""

from dataclasses import dataclass
from statistics import mean

G = 9.81


@dataclass
class Leg:
    t0: float
    t1: float
    title: str
    ias_kmh: float
    bank_deg: float
    hdg: float
    air_w_ms: float
    te_ms: float
    sink_ms: float          # measured: air_w − te
    pred_sink_ms: float     # polar, or None
    weight_kg: float
    flap: str

    @property
    def dur_s(self):
        return self.t1 - self.t0

    @property
    def delta_ms(self):
        """measured − predicted sink. positive: the glider did worse than its polar."""
        return None if self.pred_sink_ms is None else self.sink_ms - self.pred_sink_ms


def find_legs(rows, min_s=15.0, max_bank=10.0, ias_tol=10.0):
    legs, seg = [], []

    def close():
        if seg and seg[-1]["t"] - seg[0]["t"] >= min_s:
            legs.append(_summarize(seg))

    for r in rows:
        steady = r["ok"] and not r.get("brakes") and abs(r["bank_deg"]) <= max_bank
        if steady and (not seg or (abs(r["ias_kmh"] - seg[0]["ias_kmh"]) <= ias_tol
                                   and r.get("title") == seg[0].get("title"))):
            seg.append(r)
            continue
        close()
        seg = [r] if steady else []
    close()
    return legs


def _summarize(s):
    a, b = s[0], s[-1]
    dur = b["t"] - a["t"]
    va, vb = a["tas_kmh"] / 3.6, b["tas_kmh"] / 3.6
    te = (b["alt_m"] - a["alt_m"] + (vb * vb - va * va) / (2 * G)) / dur
    air_w = mean(r["air_w_ms"] for r in s)
    preds = [r["pred_sink_ms"] for r in s if r.get("pred_sink_ms") is not None]
    flaps = sorted({int(r["flap_idx"]) for r in s if isinstance(r.get("flap_idx"), (int, float))})
    return Leg(
        t0=a["t"], t1=b["t"], title=a.get("title") or "",
        ias_kmh=mean(r["ias_kmh"] for r in s),
        bank_deg=mean(abs(r["bank_deg"]) for r in s),
        hdg=a.get("hdg_true") or 0.0,
        air_w_ms=air_w, te_ms=te, sink_ms=air_w - te,
        pred_sink_ms=mean(preds) if len(preds) >= len(s) / 2 else None,
        weight_kg=mean(r["weight_kg"] for r in s),
        flap=",".join(map(str, flaps)) if flaps else "",
    )
