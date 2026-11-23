"""Put the extracted life tables on stable company ids and derive single-quarter figures.

Writes:
  data/processed/life_panel.csv.gz     life_long + company_id, stream_id, single-quarter value and how it was derived
  data/processed/life_streams.csv.gz   the same, summed to continuity streams (a company plus everything it absorbed)
  validation/name_timeline.csv      every name IRA printed, the id it was mapped to, first and last period seen
  validation/unmapped_names.csv     names no pattern matched (the build fails while this is non-empty)

IRA figures are year to date. The single-quarter figure for Qn is YTD(Qn) - YTD(Qn-1) of the same
year; Q1 is its own single quarter. If the previous quarter is missing the single quarter is left
blank and flagged rather than guessed. Stock tables (balance sheets) are not differenced.
"""
import collections
import os
import sys

import pandas as pd

from .common import PROCESSED, VALIDATION, load_refs, norm_name, slug, write_csv


def map_names(df, companies, names):
    """Map printed names to ids. A pattern may be limited to a range of quarters (valid_from /
    valid_to as YYYYQn), because IRA has reused one printed name for two companies."""
    cache = {}
    for n, y, q in df[["raw_name", "year", "quarter"]].drop_duplicates().itertuples(index=False):
        period = f"{y}Q{q}"
        cid = ""
        for rx, row in names.items:
            lo, hi = row.get("valid_from") or "0000Q0", row.get("valid_to") or "9999Q9"
            if lo <= period <= hi and rx.search(norm_name(n)):
                cid = row["company_id"]
                break
        cache[(n, y, q)] = cid
    df["company_id"] = [cache[k] for k in zip(df["raw_name"], df["year"], df["quarter"])]
    # Reinsurers are printed among the insurers on some pages: take the segment from the company list.
    known = df["company_id"].map(lambda c: companies.get(c, {}).get("segment", ""))
    df["segment"] = known.where(known != "", df["segment"])
    df["stream_id"] = df["company_id"].map(lambda c: companies.get(c, {}).get("stream_id", c))
    df["display_name"] = df["company_id"].map(lambda c: companies.get(c, {}).get("display_name", ""))
    return df


def event_quarters(events):
    """(stream_id, year, quarter) for mergers/transfers with a known effective date."""
    out = set()
    for e in events:
        if e["event_type"] in ("merger", "portfolio_transfer") and e["effective_date"]:
            y, mth = int(e["effective_date"][:4]), int(e["effective_date"][5:7])
            out.add((e["stream_id"], y, (mth - 1) // 3 + 1))
    return out


def single_quarter(df):
    df = df.sort_values(["company_id", "table_key", "line_key", "year", "quarter"]).copy()
    df["q_value"] = float("nan")
    df["q_flag"] = "stock"
    f = df[df["table_kind"] == "flow"]
    g = f.groupby(["company_id", "table_key", "line_key", "year"], sort=False)
    prev_val, prev_q = g["value"].shift(1), g["quarter"].shift(1)
    q1 = f["quarter"] == 1
    diff = (~q1) & (prev_q == f["quarter"] - 1)
    df.loc[f.index, "q_flag"] = "previous_quarter_missing"
    df.loc[f.index[q1], "q_value"] = f.loc[q1, "value"]
    df.loc[f.index[q1], "q_flag"] = "q1_is_ytd"
    df.loc[f.index[diff], "q_value"] = (f["value"] - prev_val)[diff]
    df.loc[f.index[diff], "q_flag"] = "ytd_difference"
    return df


def main():
    companies, names, _, _, events = load_refs()
    df = pd.read_csv(os.path.join(PROCESSED, "life_long.csv.gz"))
    if df.empty:
        print("life_long.csv.gz is empty - run kli.extract first")
        return 1
    df = map_names(df, companies, names)
    df["line_key"] = df["line_std"].fillna("")
    df.loc[df["line_key"] == "", "line_key"] = df.loc[df["line_key"] == "", "line_raw"].map(lambda s: "raw:" + slug(s, 50))

    # Name timeline and unmapped names, for review.
    tl = (df.groupby(["raw_name", "company_id", "segment"])
            .agg(first_year=("year", "min"), last_year=("year", "max"), periods=("period_end", "nunique"))
            .reset_index().sort_values(["company_id", "first_year"]))
    tl.to_csv(os.path.join(VALIDATION, "name_timeline.csv"), index=False)
    unmapped = tl[tl["company_id"] == ""]
    unmapped.to_csv(os.path.join(VALIDATION, "unmapped_names.csv"), index=False)

    # One value per company, period, table and line. Two printed names mapping to one id in the
    # same period would be double counting: keep the first, record the clash.
    keys = ["company_id", "year", "quarter", "table_key", "line_key"]
    mapped = df[df["company_id"] != ""].copy()
    dup = mapped.duplicated(keys, keep="first")
    mapped.loc[dup].to_csv(os.path.join(VALIDATION, "duplicate_company_rows.csv"), index=False)
    mapped = mapped.loc[~dup]

    panel = single_quarter(mapped)
    ev = event_quarters(events)
    hit = panel.apply(lambda r: (r["stream_id"], r["year"], r["quarter"]) in ev, axis=1)
    panel.loc[hit & (panel["q_flag"] == "ytd_difference"), "q_flag"] = "absorption_quarter"
    panel.to_csv(os.path.join(PROCESSED, "life_panel.csv.gz"), index=False)

    streams = (panel.groupby(["stream_id", "year", "quarter", "period_end", "table_key", "table_kind", "line_key"])
                     .agg(value=("value", "sum"), q_value=("q_value", lambda s: s.sum(min_count=len(s))),
                          companies=("company_id", lambda s: "+".join(sorted(set(s)))))
                     .reset_index())
    streams.to_csv(os.path.join(PROCESSED, "life_streams.csv.gz"), index=False)
    print(f"{len(panel)} panel rows, {panel['company_id'].nunique()} companies, "
          f"{streams['stream_id'].nunique()} streams; {len(unmapped)} unmapped names")
    return 0


if __name__ == "__main__":
    sys.exit(main())
