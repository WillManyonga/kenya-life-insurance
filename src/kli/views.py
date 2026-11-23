"""Build the consolidated annual file, the Excel workbook and the data behind the explorer page.

Writes:
  data/processed/life_annual_by_stream.csv   full-year (Q4 year-to-date) figures per continuity stream
  data/processed/life_annual_by_company.csv  the same per legal company
  data/processed/life_consolidated.xlsx      the above plus the name map, events and flags, for Excel users
  site/data/life.json                         everything the explorer page reads
"""
import datetime as dt
import json
import os
import sys

import pandas as pd

from .common import CONFIG, PROCESSED, REF, SITE, VALIDATION, read_csv

PREMIUM_SOURCES = ["gross_premium_by_class", "revenue_combined"]
PROFIT_LINES = [("profit_loss", "profit_before_tax")]
CLASSES = ["life_assurance", "annuities", "pensions", "personal_pensions", "deposit_admin", "group_life",
           "group_credit", "permanent_health", "investments"]


def pick(df, key, pairs):
    """For each entity-year, take the first (table, line) in `pairs` that has a value."""
    out = {}
    for t, line in pairs:
        s = df[(df.table_key == t) & (df.line_key == line)].groupby([key, "year"])["value"].sum()
        for k, v in s.items():
            out.setdefault(k, (v, t))
    return out


def annual(df, key):
    q4 = df[df.quarter == 4]
    gwp = pick(q4, key, [(t, "gross_premium") for t in PREMIUM_SOURCES])
    pbt = pick(q4, key, PROFIT_LINES)
    cls = q4[(q4.table_key == "gross_premium_by_class") & (q4.line_key.isin(CLASSES))]
    q4 = q4[q4.table_key.isin(PREMIUM_SOURCES + ["profit_loss"])]
    cls = cls.groupby([key, "year", "line_key"])["value"].sum().unstack(fill_value=0)
    rows = []
    for k in sorted(set(gwp) | set(pbt)):
        r = {key: k[0], "year": k[1]}
        r["gross_premium_kes000"], r["premium_source"] = gwp.get(k, (None, ""))
        r["profit_kes000"], r["profit_source"] = pbt.get(k, (None, ""))
        for c in CLASSES:
            r[f"prem_{c}"] = float(cls.loc[k, c]) if k in cls.index and c in cls.columns else None
        rows.append(r)
    a = pd.DataFrame(rows)
    if a.empty:
        return a
    a["profit_margin"] = a["profit_kes000"] / a["gross_premium_kes000"]
    tot = a.groupby("year")["gross_premium_kes000"].transform("sum")
    a["market_share"] = a["gross_premium_kes000"] / tot
    a["rank"] = a.groupby("year")["gross_premium_kes000"].rank(ascending=False, method="first")
    return a.sort_values(["year", "rank"])


def main():
    panel = pd.read_csv(os.path.join(PROCESSED, "life_panel.csv.gz"))
    streams = pd.read_csv(os.path.join(PROCESSED, "life_streams.csv.gz"))
    companies = {r["company_id"]: r for r in read_csv(os.path.join(REF, "life_companies.csv"))}
    events = read_csv(os.path.join(REF, "corporate_events.csv"))
    fx = {int(r["year"]): float(r["kes_per_usd"]) for r in read_csv(os.path.join(CONFIG, "fx_kes_usd.csv")) if r["kes_per_usd"]}
    flags = pd.read_csv(os.path.join(VALIDATION, "quality_flags.csv"))

    by_stream = annual(streams, "stream_id")
    by_company = annual(panel, "company_id")
    if by_stream.empty:
        print("no full-year premium found - check validation/sheet_inventory.csv and reference/line_map.csv")
        return 1
    stream_names = {}
    for c in companies.values():
        if c["company_id"] == c["stream_id"] or c["stream_id"] not in stream_names:
            stream_names[c["stream_id"]] = c["display_name"]
    by_stream.insert(1, "display_name", by_stream["stream_id"].map(stream_names))
    stream_seg = {c["stream_id"]: c["segment"] for c in companies.values()}
    by_stream.insert(2, "segment", by_stream["stream_id"].map(stream_seg))
    by_company.insert(1, "display_name", by_company["company_id"].map(lambda c: companies[c]["display_name"]))
    by_stream.to_csv(os.path.join(PROCESSED, "life_annual_by_stream.csv"), index=False)
    by_company.to_csv(os.path.join(PROCESSED, "life_annual_by_company.csv"), index=False)

    # Quarterly market series: single-quarter gross premium, excluding flagged returns.
    bad = set(zip(flags.company_id, flags.year, flags.quarter)) if not flags.empty else set()
    gp = panel[(panel.line_key == "gross_premium") & (panel.table_key == PREMIUM_SOURCES[0])].copy()
    if gp.empty:
        gp = panel[(panel.line_key == "gross_premium") & (panel.table_key == PREMIUM_SOURCES[1])].copy()
    gp = gp[~gp.apply(lambda r: (r.company_id, r.year, r.quarter) in bad, axis=1)]
    gp = gp[gp.segment == "insurer"]
    quarterly = (gp.groupby(["year", "quarter"]).agg(ytd=("value", "sum"), single=("q_value", "sum"),
                                                     companies=("company_id", "nunique")).reset_index())

    with pd.ExcelWriter(os.path.join(PROCESSED, "life_consolidated.xlsx")) as xw:
        pd.DataFrame({"About": [
            "Kenya long-term (life) insurance business, consolidated from IRA quarterly statistics.",
            "Figures in KSh thousands, as published by IRA (unaudited). Full-year figures are Q4 year to date.",
            "stream_id ties a company to everything it absorbed or was renamed from: see corporate_events.",
            f"Built {dt.datetime.now(dt.timezone.utc):%Y-%m-%d %H:%M} UTC from data/raw/manifest.csv."]}).to_excel(xw, sheet_name="README", index=False)
        by_stream.to_excel(xw, sheet_name="annual_by_stream", index=False)
        by_company.to_excel(xw, sheet_name="annual_by_company", index=False)
        quarterly.to_excel(xw, sheet_name="market_quarterly", index=False)
        pd.read_csv(os.path.join(VALIDATION, "name_timeline.csv")).to_excel(xw, sheet_name="name_timeline", index=False)
        pd.DataFrame(events).to_excel(xw, sheet_name="corporate_events", index=False)
        pd.DataFrame(companies.values()).to_excel(xw, sheet_name="companies", index=False)
        flags.to_excel(xw, sheet_name="quality_flags", index=False)

    def clean(v):
        return None if v is None or (isinstance(v, float) and pd.isna(v)) else v

    data = {
        "built": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d"),
        "units": "KSh thousands",
        "fx": fx,
        "classes": CLASSES,
        "streams": {},
        "quarterly": [{k: clean(v) for k, v in r.items()} for r in quarterly.to_dict("records")],
        "events": events,
        "flags": flags.fillna("").to_dict("records"),
    }
    outliers = set()
    if not flags.empty:
        o = flags[flags.flag == "profit_outlier"]
        outliers = set(zip(o.company_id, o.year.astype(int)))
    for sid, g in by_stream.groupby("stream_id"):
        members = sorted(set(panel.loc[panel.stream_id == sid, "company_id"]))
        data["streams"][sid] = {
            "name": stream_names.get(sid, sid),
            "segment": stream_seg.get(sid, "insurer"),
            "companies": [{"id": c, "name": companies[c]["display_name"], "notes": companies[c]["notes"]} for c in members],
            "years": {int(r["year"]): {"gwp": clean(r["gross_premium_kes000"]), "profit": clean(r["profit_kes000"]),
                                       "profit_flag": bool(members) and any((c, int(r["year"])) in outliers for c in members),
                                       "classes": {c: clean(r[f"prem_{c}"]) for c in CLASSES}}
                      for _, r in g.iterrows()},
        }
    os.makedirs(os.path.join(SITE, "data"), exist_ok=True)
    with open(os.path.join(SITE, "data", "life.json"), "w") as f:
        json.dump(data, f, separators=(",", ":"), default=float)
    print(f"annual rows: {len(by_stream)} streams-years; site data written")
    return 0


if __name__ == "__main__":
    sys.exit(main())
