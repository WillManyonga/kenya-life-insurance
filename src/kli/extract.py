"""Extract every long-term (life) business table from IRA quarterly statistics workbooks.

Reads data/raw/quarterly/YYYY/IRA_YYYY_QN_Industry_Statistics.xlsx and writes:

  data/processed/life_long.csv.gz        one row per period, table, company and line, as printed
  data/processed/life_printed_totals.csv   IRA's own TOTAL / INDUSTRY rows, kept for validation
  validation/sheet_inventory.csv      every sheet seen, whether it was read, its title and layout

IRA changes its layout often, so nothing here depends on cell positions:
  * a sheet is a life table if its title (or name) mentions LONG TERM or LIFE and not GENERAL;
  * the table type comes from reference/table_map.csv, matched on the title;
  * the company axis is found either as a header cell reading Company / Insurer, or, for sheets
    printed with companies across the columns, as the row where most cells are known insurer names.
Figures are kept as IRA prints them: KSh thousands, year to date, unaudited.
"""
import glob
import os
import re
import sys
import warnings

import openpyxl

from .common import PROCESSED, RAW, ROOT, VALIDATION, load_refs, norm, norm_name, num, period_end, sha256, slug, write_csv

warnings.filterwarnings("ignore")
LIFE = re.compile(r"LONG[\s\-]?TERM|LIFE ASSURANCE|LIFE INSURANCE BUSINESS|GROUP LIFE|ANNUITIES BUSINESS|GROUP CREDIT|"
                  r"INVESTMENTS BUSINESS|LINKED INVESTMENTS|PERMANENT HEALTH|PENSIONS BUSINESS|DEPOSIT ADMINISTRATION", re.I)
NOT_LIFE = re.compile(r"GENERAL INSURANCE|GENERAL BUSINESS|NON[\s\-]?LIFE|SHORT[\s\-]?TERM|MICRO", re.I)
CONTINUED = re.compile(r"^CONTINUE[DS]", re.I)
COMPANY_HDR = re.compile(r"^(NAME OF (THE )?)?(COMPANY|INSURER|INSURANCE COMPANY|COMPANY NAME)S?$", re.I)
TOTAL_ROW = re.compile(r"^(GRAND )?TOTALS?\b|^MARKET TOTAL|^INDUSTRY|^SUB.?TOTAL", re.I)
SEG_ROW = {"INSURERS": "insurer", "INSURER": "insurer", "REINSURERS": "reinsurer", "REINSURER": "reinsurer",
           "REINSURES": "reinsurer", "RE-INSURERS": "reinsurer"}


def sheet_title(rows):
    best = ""
    for r in rows[:8]:
        for c in r[:12]:
            if isinstance(c, str) and len(norm(c)) > len(best) and len(norm(c)) > 15:
                best = norm(c)
        if best:
            return best
    return best


def is_micro(sheet, title):
    return bool(re.search(r"micro|_m$|\d+m$", sheet, re.I)) or "MICRO" in title.upper()


def header_labels(rows, h, start, end):
    """Column labels from the header row, prefixed by a merged parent row above when there is one."""
    top = rows[h - 1] if h > 0 else ()
    parents, carry = [], ""
    texts_above = sum(1 for c in top[start:end] if isinstance(c, str) and c.strip())
    for j in range(start, end):
        c = top[j] if j < len(top) else None
        if texts_above >= 2 and isinstance(c, str) and c.strip():
            carry = norm(c)
        parents.append(carry if texts_above >= 2 else "")
    labels = []
    for k, j in enumerate(range(start, end)):
        c = rows[h][j] if j < len(rows[h]) else None
        lab = norm(c) if c not in (None, "") else ""
        p = parents[k]
        labels.append(f"{p} | {lab}" if p and lab and p != lab else (lab or p))
    seen = {}
    for k, lab in enumerate(labels):  # IRA sometimes prints a column heading twice
        if lab:
            seen[lab] = seen.get(lab, 0) + 1
            if seen[lab] > 1:
                labels[k] = f"{lab} #{seen[lab]}"
    return labels


def read_rowwise(rows, h, ci):
    end = max(len(r) for r in rows)
    labels = header_labels(rows, h, ci + 1, end)
    seg, data, totals = "insurer", [], []
    for i in range(h + 1, len(rows)):
        r = rows[i]
        name = r[ci] if ci < len(r) else None
        if not isinstance(name, str) or not name.strip():
            continue
        n = norm(name)
        u = n.upper().rstrip(":")
        if u in SEG_ROW:
            seg = SEG_ROW[u]
            continue
        vals = [(labels[k], r[ci + 1 + k] if ci + 1 + k < len(r) else None) for k in range(len(labels))]
        vals = [(lab, v) for lab, v in vals if lab]
        if TOTAL_ROW.search(u):
            totals.append((seg, n, vals, i + 1))
        elif any(num(v) is not None for _, v in vals):
            data.append((seg, n, vals, i + 1))
    return data, totals


def find_rowwise(rows):
    for i, r in enumerate(rows[:40]):
        for j, c in enumerate(r[:6]):
            if isinstance(c, str) and COMPANY_HDR.match(norm(c)):
                return i, j
    return None


def find_columnwise(rows, names):
    best = None
    for i, r in enumerate(rows[:40]):
        hits = [j for j, c in enumerate(r) if isinstance(c, str) and names.match(norm_name(c))]
        if len(hits) >= 3 and (best is None or len(hits) > len(best[1])):
            best = (i, hits)
    return best


def read_columnwise(rows, i, names):
    hdr = rows[i]
    cols = [(j, norm(c)) for j, c in enumerate(hdr) if isinstance(c, str) and c.strip()]
    label_col = min(j for j, _ in cols)
    company_cols = [(j, n) for j, n in cols if j != label_col]
    data, totals, seg, target_done = [], [], "insurer", False
    for j, n in company_cols:
        if data and target_done:
            break
        if n.upper().rstrip(":") in SEG_ROW:
            seg = SEG_ROW[n.upper().rstrip(":")]
            continue
        vals = []
        for k in range(i + 1, len(rows)):
            r = rows[k]
            lab = r[label_col] if label_col < len(r) else None
            if isinstance(lab, str) and lab.strip():
                vals.append((norm(lab), r[j] if j < len(r) else None))
        if TOTAL_ROW.search(n.upper()):
            # Columns to the right of IRA's TOTAL are a life/general/industry summary block, not companies.
            totals.append((seg, n, vals, j + 1))
            target_done = True
        else:
            data.append((seg, n, vals, j + 1))
    return data, totals


def appendix_no(sheet):
    m = re.search(r"(\d+)", sheet)
    return m.group(1) if m else None


def main():
    companies, names, tables, lines, _ = load_refs()
    files = sorted(glob.glob(os.path.join(RAW, "quarterly", "*", "IRA_*_Q*_Industry_Statistics.xls*")))
    # Where IRA never published a Q4 workbook (2017), the annual statistics workbook stands in for Q4.
    have_q4 = {int(re.search(r"IRA_(\d{4})_Q4_", f).group(1)) for f in files if "_Q4_" in f}
    for f in sorted(glob.glob(os.path.join(RAW, "annual", "IRA_Annual_Statistics_*.xls*"))):
        y = int(re.search(r"_(\d{4})\.", f).group(1))
        if y not in have_q4 and y >= 2015:
            files.append(f)
    out, tot, inv = [], [], []
    for path in files:
        m = re.search(r"IRA_(\d{4})_Q(\d)_", path)
        if m:
            year, q = int(m.group(1)), int(m.group(2))
        else:  # annual statistics workbook standing in for a missing Q4
            year, q = int(re.search(r"_(\d{4})\.", path).group(1)), 4
        src = os.path.relpath(path, ROOT).replace(os.sep, "/")
        digest = sha256(path)[:12]
        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
        seen, prev = {}, None  # prev: (appendix number, table) of the last life sheet, for continuation pages
        for sname in wb.sheetnames:
            rows = [tuple(r) for r in wb[sname].iter_rows(values_only=True)] or [()]
            title = sheet_title(rows)
            rec = dict(year=year, quarter=q, source_file=src, sheet=sname, title=title, life=0,
                       table_key="", layout="", rows_read=0)
            if CONTINUED.match(title):
                if not (prev and prev[0] == appendix_no(sname)):
                    inv.append(rec)
                    continue
                t, key = prev[1], prev[2]
            else:
                life = bool(LIFE.search(title)) and not NOT_LIFE.search(title) and not re.match(r"templ", sname, re.I)
                prev = None
                if not life:
                    inv.append(rec)
                    continue
                t = tables.match(title.upper()) or {"table_key": "other", "kind": "flow"}
                if t["kind"] == "skip":
                    rec.update(life=1, table_key="skip", layout="skipped")
                    inv.append(rec)
                    continue
                key = t["table_key"] if t["table_key"] != "other" else f"other:{slug(title, 40)}"
                if key in seen:  # the same table printed twice: keep both, apart
                    key = f"{key}#{sname.strip()}"
                seen[key] = sname
                prev = (appendix_no(sname), t, key)
            rec["life"] = 1
            # A sheet printed with companies across the columns has a row of company names;
            # one printed with companies down the rows never does, so test that first.
            cw, hit = find_columnwise(rows, names), find_rowwise(rows)
            if cw and (len(cw[1]) >= 5 or not hit):
                data, totals = read_columnwise(rows, cw[0], names)
                layout = "companies_in_columns"
            else:
                if not hit:
                    rec.update(table_key=key, layout="not_understood")
                    inv.append(rec)
                    continue
                data, totals = read_rowwise(rows, *hit)
                layout = "companies_in_rows"
            base = dict(year=year, quarter=q, period_end=period_end(year, q), source_file=src,
                        source_sha256_12=digest, source_sheet=sname.strip(), table_key=key,
                        table_kind=t["kind"], table_title=title)
            tk = key.split(":")[0].split("#")[0]
            for seg, name, vals, where in data:
                used = set()
                for lab, v in vals:
                    x = num(v)
                    if x is None:
                        continue
                    leaf = lab.split(" | ")[-1].upper()
                    lm = lines.match(leaf, table_key=tk) or lines.match(lab.upper(), table_key=tk)
                    std = lm["line_std"] if lm and lm["line_std"] not in used else ""
                    used.add(std)
                    out.append(dict(base, segment=seg, raw_name=name, line_raw=lab,
                                    line_std=std, value=x, source_ref=where))
            for seg, name, vals, where in totals:
                for lab, v in vals:
                    x = num(v)
                    if x is not None:
                        tot.append(dict(base, segment=seg, total_label=name, line_raw=lab, value=x, source_ref=where))
            rec.update(table_key=key, layout=layout, rows_read=len(data))
            inv.append(rec)
        wb.close()
    fields = ["year", "quarter", "period_end", "source_file", "source_sha256_12", "source_sheet", "table_key",
              "table_kind", "table_title", "segment", "raw_name", "line_raw", "line_std", "value", "source_ref"]
    write_csv(os.path.join(PROCESSED, "life_long.csv.gz"), out, fields)
    write_csv(os.path.join(PROCESSED, "life_printed_totals.csv"), tot,
              ["year", "quarter", "period_end", "source_file", "source_sheet", "table_key", "segment",
               "total_label", "line_raw", "value", "source_ref"])
    write_csv(os.path.join(VALIDATION, "sheet_inventory.csv"), inv,
              ["year", "quarter", "source_file", "sheet", "title", "life", "table_key", "layout", "rows_read"])
    print(f"{len(files)} workbooks, {len(out)} values, {len(tot)} printed-total values")
    return 0


if __name__ == "__main__":
    sys.exit(main())
