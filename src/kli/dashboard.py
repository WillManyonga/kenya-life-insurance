"""Data for the business-line dashboards: claims ratios, market share, business mix, insurer profiles.

Writes site/data/lines.json: for every insurer continuity stream, every business line and every
quarter IRA published, the year-to-date revenue-account figures the ratios are built from. The page
computes ratios itself, so a ratio is always a sum of claims over a sum of premium, never an
average of ratios.

Business lines are IRA's long-term classes, each read from its own revenue account:
  individual   Life assurance (ordinary / individual life)
  group_life   Group life
  credit_life  Group credit
  annuities    Annuities
  pensions     Pensions (from 2022 IRA also splits this into personal pensions and deposit
               administration; the pensions account still carries the total, so the series is unbroken)
  investments  Investments (linked plus non-linked from 2019)
  health       Permanent health (dropped if the market never writes any)
  total        Combined long-term revenue account
"""
import json
import os
import sys

import pandas as pd

from .common import PROCESSED, REF, SITE, VALIDATION, read_csv

LINES = [
    ("individual", "Individual life", "revenue_life_assurance"),
    ("group_life", "Group life", "revenue_group_life"),
    ("credit_life", "Credit life", "revenue_group_credit"),
    ("annuities", "Annuities", "revenue_annuities"),
    ("pensions", "Pensions & deposit admin", "revenue_pensions"),
    ("investments", "Investments", "revenue_investments"),
    ("health", "Permanent health", "revenue_permanent_health"),
    ("total", "All long-term business", "revenue_combined"),
]
METRICS = {"gross_premium": "gp", "net_premium": "np", "claims": "cl", "total_benefits": "tb",
           "surrenders": "su", "net_commissions": "co", "management_expenses": "me",
           "investment_income": "ii", "life_fund_bf": "fb", "life_fund_cf": "fc"}


def main():
    companies = {r["company_id"]: r for r in read_csv(os.path.join(REF, "life_companies.csv"))}
    stream_seg = {c["stream_id"]: c["segment"] for c in companies.values()}
    names = {}
    for c in companies.values():
        if c["company_id"] == c["stream_id"] or c["stream_id"] not in names:
            names[c["stream_id"]] = c["display_name"]

    st = pd.read_csv(os.path.join(PROCESSED, "life_streams.csv.gz"))
    st = st[st.stream_id.map(stream_seg) == "insurer"]
    periods = sorted({(int(y), int(q)) for y, q in zip(st.year, st.quarter) if y >= 2016})
    pidx = {p: i for i, p in enumerate(periods)}
    n = len(periods)

    table_to_line = {t: lid for lid, _, t in LINES}
    rev = st[st.table_key.isin(table_to_line) & st.line_key.isin(METRICS)].copy()
    rev["line"] = rev.table_key.map(table_to_line)
    rev["m"] = rev.line_key.map(METRICS)
    rev["i"] = [pidx.get((int(y), int(q))) for y, q in zip(rev.year, rev.quarter)]
    rev = rev[rev.i.notna()]

    keep_lines = [l for l in LINES  # drop lines the market barely writes (permanent health): ratios on near-zero premium mislead
                  if rev.loc[(rev.line == l[0]) & (rev.m == "gp") & (rev.quarter == 4)].groupby("year").value.sum().max() > 500_000]

    pbt = st[(st.table_key == "profit_loss") & (st.line_key == "profit_before_tax")]

    flags = pd.read_csv(os.path.join(VALIDATION, "quality_flags.csv"))
    comp_stream = {c: v["stream_id"] for c, v in companies.items()}

    out = {"periods": [f"{y}Q{q}" for y, q in periods],
           "lines": [{"id": l, "label": lab} for l, lab, _ in keep_lines],
           "units": "KSh thousands, year to date",
           "streams": {}}
    for sid, g in rev.groupby("stream_id"):
        data = {}
        for (line, m), h in g.groupby(["line", "m"]):
            arr = [None] * n
            for i, v in zip(h.i.astype(int), h.value):
                arr[i] = round(float(v))
            data.setdefault(line, {})[m] = arr
        p = [None] * n
        for y, q, v in pbt.loc[pbt.stream_id == sid, ["year", "quarter", "value"]].itertuples(index=False):
            if (int(y), int(q)) in pidx:
                p[pidx[(int(y), int(q))]] = round(float(v))
        fl = flags[(flags.flag == "ytd_falls") & (flags.company_id.map(comp_stream) == sid)]
        sj = flags[(flags.flag == "ytd_jump") & (flags.company_id.map(comp_stream) == sid)]
        out["streams"][sid] = {
            "name": names.get(sid, sid),
            "lines": data,
            "pbt": p,
            # Only a printed zero (a return not filed in time) is excluded; a small year-to-date dip
            # (usually a restatement) stays in and is listed in validation/quality_flags.csv.
            "not_filed": sorted(i for i in {pidx[(int(y), int(q))] for y, q in zip(fl.year, fl.quarter) if (int(y), int(q)) in pidx}
                                if not (data.get("total", {}).get("gp") or [None] * n)[i]),
            # Returns IRA printed with an implausible jump (e.g. Equity Life Q4 2023) are also left out.
            "suspect": sorted({pidx[(int(y), int(q))] for y, q in zip(sj.year, sj.quarter) if (int(y), int(q)) in pidx}),
        }
    with open(os.path.join(SITE, "data", "lines.json"), "w") as f:
        json.dump(out, f, separators=(",", ":"))
    size = os.path.getsize(os.path.join(SITE, "data", "lines.json"))
    print(f"lines.json: {len(out['streams'])} insurers, {len(keep_lines)} lines, {n} quarters, {size / 1e3:.0f} KB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
