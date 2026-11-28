"""IRA's quarterly claims settlement statistics: how many claims insurers paid, declined and still hold.

IRA publishes a claims settlement workbook each quarter (data/raw/claims/YYYY/, listed in
config/sources.csv as kind claims_statistics). Each table is one business and one unit:
long-term (life) claims, general liability claims and general non-liability claims, in numbers
and, from Q4 2022, in amounts (KSh thousands). Each row is an insurer's movement in the quarter:

    outstanding at the start + intimated (reported) + revived
      = paid + declined + closed as no claim + outstanding at the end

Columns are found by their headings, since IRA changed the layout several times. The approach
follows Maiden Peter's ira-kenya-data (github.com/maidenpeter/ira-kenya-data), which first worked
through these workbooks; this is an independent implementation for the life repository.

Every business is extracted. What is written to the repository is limited by config/scope.csv
(dataset "claims" or "all"): life only for now, i.e. long-term claims. Set general to yes there to
also publish the general business tables.

Writes:
  data/processed/claims_settlement.csv  period, business, unit, printed name, company and stream ids, the movement
  validation/claims_checks.csv          each table against IRA's printed industry line, and each row's movement
  validation/claims_unmapped_names.csv  long-term names no pattern matched (reported, not fatal)

The payment ratio used on the site is IRA's: claims paid / claims open in the quarter, where claims
open = paid + declined + closed + outstanding at the end.
"""
import glob
import os
import re
import sys
import warnings

import openpyxl

from .common import PROCESSED, RAW, VALIDATION, load_refs, norm, norm_name, write_csv
from .registry import scope

warnings.filterwarnings("ignore")
FIELDS = ["opening", "intimated", "revived", "revised", "paid", "declined", "closed", "declined_closed", "closing"]
HEADERS = [  # heading text -> field; the first match wins
    (r"name of|^insurer|^company", "name"),
    (r"outstanding at (the )?(beginning|start)", "opening"),
    (r"intimated and revived", "intimated"),
    (r"intimated|reported during", "intimated"),
    (r"revived", "revived"),
    (r"revised", "revised"),
    (r"total claims", None),
    (r"claims paid|paid during", "paid"),
    (r"(rejected|declined) and closed", "declined_closed"),
    (r"(declined|rejected|repudiated)", "declined"),
    (r"closed as no claims?|closed during", "closed"),
    (r"outstanding at (the )?end", "closing"),
    (r"(settlement|payment) ratio", "printed_ratio"),
]
BUSINESS_SEGMENT = {"long_term": "life", "general_liability": "general", "general_non_liability": "general"}


def classify(title):
    t = norm(title).lower()
    if re.search(r"monthly|reasons|micro", t):
        return None
    if re.search(r"long[\s-]*term|life", t):
        b = "long_term"
    elif re.search(r"non[\s-]*liability", t):
        b = "general_non_liability"
    elif "liability" in t:
        b = "general_liability"
    else:
        return None
    unit = "amount" if re.search(r"amount|kshs?\b|value", t) else "number"
    return b, unit


def title_of(rows):
    for r in rows[:8]:
        for v in r:
            if isinstance(v, str) and re.search(r"(appendix\s*\d+|analysis of|claims (settlement|statistics))", v, re.I) and len(v) > 20:
                return norm(v)
    return None


def columns(header):
    cols = {}
    for j, v in enumerate(header):
        if v is None:
            continue
        h = norm(v).lower()
        for pat, field in HEADERS:
            if re.search(pat, h):
                if field and field not in cols:
                    cols[field] = j
                break
    return cols


def num(v):
    if v is None or (isinstance(v, str) and not v.strip()):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).replace(",", "").strip()
    if s in ("-", "--", "–"):
        return 0.0
    try:
        return float(s)
    except ValueError:
        return None


def read(path):
    year, q = map(int, re.search(r"IRA_(\d{4})_Q(\d)", path).groups())
    wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
    out, totals, seen = [], [], set()
    for ws in wb.worksheets:
        rows = list(ws.iter_rows(values_only=True))
        title = title_of(rows)
        kind = classify(title) if title else None
        if not kind or kind in seen:
            continue
        h = next((i for i, r in enumerate(rows[:15]) if sum(1 for v in r if isinstance(v, str) and re.search(r"outstanding|paid|intimated", v, re.I)) >= 2), None)
        if h is None:
            continue
        # headings can sit on two rows: join each column's text
        head = [" ".join(norm(rows[k][j]) for k in (h - 1, h) if 0 <= k < len(rows) and j < len(rows[k]) and rows[k][j] is not None)
                for j in range(max(len(r) for r in rows[max(0, h - 1):h + 1]))]
        cols = columns(head)
        if "name" not in cols:
            cols["name"] = next((j for j, v in enumerate(head) if v), 0) if not re.search(r"\d", head[0] or "") else 1
        if not {"paid", "closing"} <= set(cols):
            continue
        seen.add(kind)
        for r in rows[h + 1:]:
            name = r[cols["name"]] if cols["name"] < len(r) else None
            if not isinstance(name, str) or not name.strip() or re.match(r"^\s*(source|note|\*)", name, re.I):
                continue
            vals = {f: num(r[j]) if j < len(r) else None for f, j in cols.items() if f != "name"}
            if all(vals.get(f) is None for f in ("opening", "paid", "closing")):
                continue
            rec = dict(period=f"{year}Q{q}", year=year, quarter=q, business=kind[0], unit=kind[1], raw_name=norm(name), sheet=ws.title.strip())
            rec.update({f: vals.get(f) for f in FIELDS})
            rec["printed_ratio"] = vals.get("printed_ratio")
            if re.fullmatch(r"(industry|total|industry total|grand total|market total)", norm(name).lower()):
                totals.append(rec)
                break
            out.append(rec)
    return out, totals


def main():
    companies, names, _, _, _ = load_refs()
    files = sorted(glob.glob(os.path.join(RAW, "claims", "*", "IRA_*_Q*_Claims_Statistics.xls*")))
    rows, totals, checks = [], [], []
    for f in files:
        try:
            r, t = read(f)
        except Exception as e:   # one bad workbook is reported, not fatal
            checks.append(dict(period=os.path.basename(f), business="", unit="", check="read", result="fail", detail=str(e)[:200]))
            continue
        rows += r
        totals += t
        if not r:
            checks.append(dict(period=os.path.basename(f), business="", unit="", check="tables_found", result="fail", detail="no claims table recognised"))
    # company ids for long-term rows, with the same period-aware patterns as the accounts
    cache = {}
    for r in rows:
        if r["business"] != "long_term":
            r["company_id"] = ""
            continue
        key = (r["raw_name"], r["period"])
        if key not in cache:
            cid = ""
            for rx, row in names.items:
                lo, hi = row.get("valid_from") or "0000Q0", row.get("valid_to") or "9999Q9"
                if lo <= r["period"] <= hi and rx.search(norm_name(r["raw_name"])):
                    cid = row["company_id"]
                    break
            cache[key] = cid
        r["company_id"] = cache[key]
    for r in rows:
        r["stream_id"] = companies.get(r["company_id"], {}).get("stream_id", r["company_id"]) if r["company_id"] else ""
        r["segment"] = BUSINESS_SEGMENT[r["business"]]
        out_ = sum(r[f] or 0 for f in ("paid", "declined", "closed", "declined_closed", "closing"))
        r["actionable"] = out_
        inn = sum(r[f] or 0 for f in ("opening", "intimated", "revived"))
        if r["unit"] == "number" and r["opening"] is not None:
            ok = abs(inn - out_) <= max(1, 0.005 * out_)
            checks.append(dict(period=r["period"], business=r["business"], unit=r["unit"], check="movement", result="pass" if ok else "differs",
                               detail=f"{r['raw_name']}: in {inn:.0f} vs out {out_:.0f}"))
    # each table against IRA's printed industry line
    for t in totals:
        part = [r for r in rows if (r["period"], r["business"], r["unit"]) == (t["period"], t["business"], t["unit"])]
        for f in ("paid", "closing"):
            if t[f] is None:
                continue
            s = sum(r[f] or 0 for r in part)
            ok = abs(s - t[f]) <= max(1, 0.001 * abs(t[f]))
            checks.append(dict(period=t["period"], business=t["business"], unit=t["unit"], check=f"total_{f}", result="pass" if ok else "differs",
                               detail=f"rows {s:.0f} vs printed {t[f]:.0f}"))
    # Isolated spikes: a count far above the same insurer's usual quarters (Kenyan Alliance printed
    # 774,075 claims paid in Q1 2023 against about 1,300 in the quarters around it; Monarch 47,636 in
    # Q4 2025 against under 100). Such a return is kept in the file, flagged, and left out of the site.
    import statistics
    groups = {}
    for r in rows:
        groups.setdefault((r["stream_id"] or r["raw_name"].upper(), r["business"], r["unit"]), []).append(r)
    for (who, b, u), g in groups.items():
        for f in ("paid", "intimated", "closing"):
            vals = [r[f] for r in g if r[f] is not None]
            for r in g:
                v, others = r[f], [x for x in vals if x is not r[f]]
                if v is None or len(others) < 3:
                    continue
                med = statistics.median(others)
                if u == "number" and v > 8 * max(med, 1) and v - med > 2000:
                    r["suspect"] = f"{f} {v:.0f} against a usual {med:.0f}"
                    checks.append(dict(period=r["period"], business=b, unit=u, check="spike", result="flagged", detail=f"{r['raw_name']}: {r['suspect']}"))
    for r in rows:   # the amount row of a flagged quarter goes with it
        r.setdefault("suspect", "")
    flagged = {(r["stream_id"] or r["raw_name"].upper(), r["business"], r["period"]) for r in rows if r["suspect"]}
    for r in rows:
        if not r["suspect"] and (r["stream_id"] or r["raw_name"].upper(), r["business"], r["period"]) in flagged:
            r["suspect"] = "count flagged in the same quarter"
    unm = sorted({(r["raw_name"], r["period"]) for r in rows if r["business"] == "long_term" and not r["company_id"]})
    write_csv(os.path.join(VALIDATION, "claims_unmapped_names.csv"), [dict(raw_name=n, period=p) for n, p in unm], ["raw_name", "period"])
    write_csv(os.path.join(VALIDATION, "claims_checks.csv"), checks, ["period", "business", "unit", "check", "result", "detail"])
    keep = scope("claims")
    cols = ["period", "year", "quarter", "business", "segment", "unit", "raw_name", "company_id", "stream_id"] + FIELDS + ["actionable", "printed_ratio", "suspect", "sheet"]
    pub = [r for r in rows if r["segment"] in keep]
    write_csv(os.path.join(PROCESSED, "claims_settlement.csv"), pub, cols)
    write_csv(os.path.join(VALIDATION, "claims_printed_totals.csv"), [t for t in totals if BUSINESS_SEGMENT[t["business"]] in keep],
              ["period", "business", "unit", "raw_name"] + FIELDS)
    fails = sum(1 for c in checks if c["result"] != "pass")
    print(f"claims: {len(files)} workbooks, {len(rows)} rows ({len(pub)} published: {', '.join(sorted(keep))}); "
          f"{len(unm)} unmapped long-term names; {fails} checks not passing")
    return 0


if __name__ == "__main__":
    sys.exit(main())
