"""Print the steady legs of a recording, with polar predictions.

Same analysis as the HTML report's table (msfsdiag.analysis), as text.

usage: python scripts/steady_segments.py <run.jsonl> [--since <unix t>] [--min-sec 15] [--max-bank 10] [--ias-tol 10]
"""

import argparse
from datetime import datetime

from msfsdiag.analysis import legs, polar, run
from msfsdiag.config import load as load_config


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("file")
    ap.add_argument("--since", type=float, default=0)
    ap.add_argument("--min-sec", type=float, default=15)
    ap.add_argument("--max-bank", type=float, default=10)
    ap.add_argument("--ias-tol", type=float, default=10)
    args = ap.parse_args()

    polars = polar.load_polars(load_config().data_dir / "polars")
    r = run.load(args.file, polars)
    rows = [x for x in r.rows if x["t"] >= args.since]
    f = lambda v, n=2: "    -" if v is None else f"{v:5.{n}f}"
    print(f"{'start':>8} {'dur s':>5} {'IAS':>4} {'bank':>4} {'air_w':>5} {'climb':>5} {'sink':>5} {'pred':>5} {'delta':>5}  kg  flap")
    for g in legs.find_legs(rows, args.min_sec, args.max_bank, args.ias_tol):
        print(f"{datetime.fromtimestamp(g.t0):%H:%M:%S} {g.dur_s:5.0f} {g.ias_kmh:4.0f} {g.bank_deg:4.0f} "
              f"{f(g.air_w_ms)} {f(g.te_ms)} {f(g.sink_ms)} {f(g.pred_sink_ms)} {f(g.delta_ms)} {g.weight_kg:4.0f}  {g.flap}")


if __name__ == "__main__":
    main()
