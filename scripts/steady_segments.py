"""Find steady, straight stretches in a probe recording and average them.

A segment is steady when, for at least --min-sec seconds: airborne, not paused or
slewing (IAS > 40 km/h), |bank| < --max-bank, and IAS stays within ±--ias-tol km/h
of the segment's first sample.

Per segment: mean IAS, mean air-mass vertical speed (AMBIENT WIND Y), mean aircraft
vertical speed, and their difference. "implied sink" = air_w - vs is the sink rate
the glider shows relative to the air; compare it with the polar at that IAS/weight.

usage: python scripts/steady_segments.py data/raw/<file>.jsonl [--since <unix t>]
"""

import argparse
import json
from datetime import datetime
from statistics import mean


def segments(rows, min_sec, max_bank, ias_tol):
    seg = []
    for r in rows:
        ok = (
            not r.get("on_ground")
            and (r.get("ias_kmh") or 0) > 40
            and abs(r.get("bank_deg") or 99) < max_bank
            and (not seg or abs(r["ias_kmh"] - seg[0]["ias_kmh"]) <= ias_tol)
        )
        if ok:
            seg.append(r)
            continue
        if seg and seg[-1]["t"] - seg[0]["t"] >= min_sec:
            yield seg
        seg = [r] if (r.get("ias_kmh") or 0) > 40 and abs(r.get("bank_deg") or 99) < max_bank else []
    if seg and seg[-1]["t"] - seg[0]["t"] >= min_sec:
        yield seg


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("file")
    ap.add_argument("--since", type=float, default=0)
    ap.add_argument("--min-sec", type=float, default=15)
    ap.add_argument("--max-bank", type=float, default=10)
    ap.add_argument("--ias-tol", type=float, default=10)
    args = ap.parse_args()

    rows = [json.loads(line) for line in open(args.file, encoding="utf-8")]
    rows = [r for r in rows if r["t"] >= args.since]
    print(f"{'start':>8} {'dur s':>5} {'IAS':>5} {'hdg':>4} {'air_w':>6} {'vs':>6} "
          f"{'dalt/s':>6} {'te/s':>6} {'sink(te)':>8} {'kg':>4} {'flap':>4}  wind")
    for s in segments(rows, args.min_sec, args.max_bank, args.ias_tol):
        dur = s[-1]["t"] - s[0]["t"]
        air_w = mean(r["air_w_ms"] for r in s)
        vs = mean(r["vs_ms"] for r in s)
        # altitude change over the segment: a cross-check on the VS simvar
        dalt = (s[-1]["alt_m"] - s[0]["alt_m"]) / dur
        # total-energy climb rate: altitude plus kinetic energy height, so speed
        # traded for height (or the reverse) doesn't count as lift or sink
        v0, v1 = s[0]["tas_kmh"] / 3.6, s[-1]["tas_kmh"] / 3.6
        te = dalt + (v1 * v1 - v0 * v0) / (2 * 9.81) / dur
        flaps = sorted({r.get("flap_idx") for r in s if r.get("flap_idx") is not None})
        print(f"{datetime.fromtimestamp(s[0]['t']):%H:%M:%S} {dur:5.0f} "
              f"{mean(r['ias_kmh'] for r in s):5.0f} {mean(r['hdg_true'] for r in s):4.0f} "
              f"{air_w:6.2f} {vs:6.2f} {dalt:6.2f} {te:6.2f} {air_w - te:8.2f} "
              f"{mean(r['weight_kg'] for r in s):4.0f} {','.join(f'{f:.0f}' for f in flaps) or '?':>4}  "
              f"{mean(r['wind_dir'] for r in s):3.0f}/{mean(r['wind_kt'] for r in s):.0f}kt")


if __name__ == "__main__":
    main()
