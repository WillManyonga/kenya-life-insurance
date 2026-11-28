"""Site data for the Claims settlement and Registered insurers tabs.

    site/data/claims.json    the published claims movement per quarter, for the market and each stream
    site/data/registry.json  the published registered insurers by year, and IRA's printed counts

Both read only what claims.py and registry.py wrote, so they follow config/scope.csv.
"""
import json
import os
import sys

import pandas as pd

from .common import PROCESSED, REF, SITE, read_csv

CODES = {"opening": "o", "intimated": "i", "revived": "rv", "paid": "p", "declined": "d", "closed": "c",
         "declined_closed": "dc", "closing": "cl", "actionable": "a"}


def names():
    out = {}
    for c in read_csv(os.path.join(REF, "life_companies.csv")):
        if c["company_id"] == c["stream_id"] or c["stream_id"] not in out:
            out[c["stream_id"]] = c["display_name"]
    return out


def claims():
    p = os.path.join(PROCESSED, "claims_settlement.csv")
    if not os.path.exists(p):
        return None
    df = pd.read_csv(p)
    if df.empty:
        return None
    periods = sorted(df.period.unique(), key=lambda s: (int(s[:4]), int(s[5])))
    pidx = {p: i for i, p in enumerate(periods)}
    n = len(periods)
    out = {"periods": periods, "businesses": sorted(df.business.unique()), "market": {}, "streams": {}, "names": names()}
    for (b, u), g in df.groupby(["business", "unit"]):
        m = g.groupby("period")[list(CODES)].sum(min_count=1)
        out["market"].setdefault(b, {})[u] = {CODES[f]: [None if pd.isna(m[f].get(p)) else round(float(m[f].get(p)))
                                                          for p in periods] for f in CODES}
        for sid, h in g[g.stream_id.notna() & (g.stream_id != "")].groupby("stream_id"):
            h = h.groupby("period")[list(CODES)].sum(min_count=1)
            arr = {}
            for f in CODES:
                a = [None] * n
                for per, v in h[f].items():
                    if not pd.isna(v):
                        a[pidx[per]] = round(float(v))
                if any(x is not None for x in a):
                    arr[CODES[f]] = a
            out["streams"].setdefault(sid, {}).setdefault(b, {})[u] = arr
    return out


def registry():
    p = os.path.join(PROCESSED, "registered_insurers.csv")
    if not os.path.exists(p):
        return None
    df = pd.read_csv(p, dtype=str).fillna("")
    pc = os.path.join(PROCESSED, "registered_counts_printed.csv")
    printed = {}
    if os.path.exists(pc):
        for r in read_csv(pc):
            printed.setdefault(r["year"], {})[r["type"]] = int(r["companies"])
    return {"years": sorted({int(y) for y in df.year}), "names": names(), "printed": printed,
            "rows": [dict(y=int(r.year), n=r.name, t=r.type, s=r.segment, c=r.classes, id=r.company_id, src=r.source)
                     for r in df.itertuples()]}


def main():
    os.makedirs(os.path.join(SITE, "data"), exist_ok=True)
    for name, fn in (("claims", claims), ("registry", registry)):
        d = fn()
        if d is None:
            print(f"sitedata: no {name} data yet")
            continue
        with open(os.path.join(SITE, "data", f"{name}.json"), "w") as f:
            json.dump(d, f, separators=(",", ":"))
        print(f"sitedata: wrote {name}.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
