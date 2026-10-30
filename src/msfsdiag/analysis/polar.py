"""Glider polars from data/polars/*.json, and predicted sink for a flight state.

Each polar file has one or more sets (one per reference mass). A set is fitted
with a parabola sink(v) = a·v² + b·v + c in IAS (km/h):
- with 3+ points: least squares through them
- with a min_sink point: the min-sink point is the vertex; each other point is
  mirrored across it, so the fit has its minimum there

Predicted sink for an actual state:
- mass: pick the set with the nearest mass, scale by f = sqrt(m / m_ref)
  (speeds and sinks both scale by f at the same lift coefficient)
- bank: sink / cos(bank)^1.5 (same speed, load factor 1/cos)
- altitude: the polar is IAS at sea level; true sink = sink · TAS / IAS
"""

import json
import math
import re
from dataclasses import dataclass
from pathlib import Path


def _fit_parabola(pts):
    """Least-squares a, b, c for y = a x² + b x + c."""
    n = len(pts)
    if n < 3:
        raise ValueError("need at least 3 points to fit a parabola")
    sx = [sum(x ** k for x, _ in pts) for k in range(5)]
    sy = [sum(y * x ** k for x, y in pts) for k in range(3)]
    # normal equations, rows for c, b, a
    m = [
        [sx[0], sx[1], sx[2], sy[0]],
        [sx[1], sx[2], sx[3], sy[1]],
        [sx[2], sx[3], sx[4], sy[2]],
    ]
    for i in range(3):  # gaussian elimination with partial pivoting
        p = max(range(i, 3), key=lambda r: abs(m[r][i]))
        m[i], m[p] = m[p], m[i]
        for r in range(3):
            if r != i:
                f = m[r][i] / m[i][i]
                m[r] = [m[r][k] - f * m[i][k] for k in range(4)]
    c, b, a = (m[i][3] / m[i][i] for i in range(3))
    return a, b, c


@dataclass(frozen=True)
class PolarSet:
    mass_kg: float
    a: float
    b: float
    c: float

    def sink(self, ias_kmh: float) -> float:
        return self.a * ias_kmh ** 2 + self.b * ias_kmh + self.c


@dataclass(frozen=True)
class Polar:
    name: str
    path: Path
    status: str
    match_titles: tuple
    sets: tuple
    valid_ias_kmh: tuple = (0.0, 1e9)  # at the reference mass; scaled with mass like the curve
    has_flaps: bool = True
    flap_names: tuple = ()  # ((index str, name), ...)

    def matches(self, title: str) -> bool:
        return any(re.search(re.escape(m), title or "", re.I) for m in self.match_titles)

    def sink(self, ias_kmh, mass_kg, bank_deg=0.0, tas_kmh=None):
        """Predicted true sink rate (m/s, positive down), or None outside the usable range."""
        if not ias_kmh or ias_kmh < 40 or mass_kg is None:
            return None
        s = min(self.sets, key=lambda st: abs(st.mass_kg - mass_kg))
        f = math.sqrt(mass_kg / s.mass_kg)
        lo, hi = self.valid_ias_kmh
        if not lo <= ias_kmh / f <= hi:
            return None
        sink = s.sink(ias_kmh / f) * f
        cb = math.cos(math.radians(min(abs(bank_deg or 0.0), 75.0)))
        sink /= cb ** 1.5
        if tas_kmh:
            sink *= tas_kmh / ias_kmh
        return sink


def to_reference(polar_set, ias_kmh, sink_ms, mass_kg, bank_deg=0.0, tas_kmh=None):
    """Undo the corrections in Polar.sink: a measured (IAS, true sink) at some mass,
    bank and altitude, as the equivalent straight-flight, sea-level point at the
    set's reference mass. Returns (ias_kmh, sink_ms) on the set's own curve scale."""
    s = sink_ms
    if tas_kmh:
        s *= ias_kmh / tas_kmh
    s *= math.cos(math.radians(min(abs(bank_deg or 0.0), 75.0))) ** 1.5
    f = math.sqrt(mass_kg / polar_set.mass_kg)
    return ias_kmh / f, s / f


def load_polar(path: Path) -> Polar:
    d = json.loads(Path(path).read_text(encoding="utf-8"))
    sets = []
    for st in d["sets"]:
        pts = [(p["ias_kmh"], p["sink_ms"]) for p in st.get("points", [])]
        ms = st.get("min_sink")
        if ms:
            v0, s0 = ms["ias_kmh"], ms["sink_ms"]
            pts = [(v0, s0)] + pts + [(2 * v0 - v, s) for v, s in pts]
        sets.append(PolarSet(st["mass_kg"], *_fit_parabola(pts)))
    valid = d.get("valid_ias_kmh")
    return Polar(d["aircraft"], Path(path), d.get("status", ""), tuple(d.get("match_titles", ())),
                 tuple(sets), tuple(valid) if valid else (0.0, 1e9),
                 d.get("flaps", True), tuple(d.get("flap_index_names", {}).items()))


def load_polars(directory: Path) -> list:
    return [load_polar(p) for p in sorted(Path(directory).glob("*.json"))]


def for_title(polars, title):
    return next((p for p in polars if p.matches(title)), None)
