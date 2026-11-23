"""Check the life tables against themselves and against IRA's printed totals.

Checks
  1. names      every printed company name maps to a company id (hard failure if not)
  2. totals     company rows add to IRA's printed TOTAL / INDUSTRY row, column by column
  3. classes    in the premium-by-class table, the classes add to the company's total
  4. ytd        a year-to-date flow should not fall from one quarter to the next (premium lines)
  5. coverage   which tables were found in which quarter

Writes validation/checks.csv (every check), validation/quality_flags.csv (returns to treat with care)
and validation/SUMMARY.md. Exits non-zero only on hard failures (unmapped names, no data), so a
scheduled run still publishes when IRA's own totals are off; those are listed, not hidden.
"""
import os
import sys

import pandas as pd

from .common import PROCESSED, VALIDATION

CLASS_LINES = {"ordinary_life", "group_life", "group_credit", "deposit_admin_pensions", "annuities",
               "investment_unit_linked", "health", "micro"}


def tol(x):
    return max(1.0, abs(x) * 0.001)


def check_totals(long, totals):
    out = []
    long = long.copy()
    long["k"] = long["line_raw"]
    for (y, q, t), tt in totals.groupby(["year", "quarter", "table_key"]):
        rows = long[(long.year == y) & (long.quarter == q) & (long.table_key == t)]
        for _, r in tt.iterrows():
            lab = str(r["total_label"]).upper()
            scope = rows if any(w in lab for w in ("INDUSTRY", "MARKET", "GRAND")) else rows[rows.segment == r["segment"]]
            s = scope.loc[scope.k == r["line_raw"], "value"].sum()
            ok = abs(s - r["value"]) <= tol(r["value"])
            out.append(dict(check="totals", year=y, quarter=q, table_key=t, item=f"{r['total_label']} / {r['line_raw']}",
                            expected=r["value"], actual=round(s, 2), passed=int(ok)))
    return out


def check_classes(panel):
    out = []
    p = panel[panel.table_key == "gross_premium_by_class"]
    for (c, y, q), g in p.groupby(["company_id", "year", "quarter"]):
        total = g.loc[g.line_key == "gross_premium", "value"]
        parts = g.loc[g.line_key.isin(CLASS_LINES), "value"]
        if total.empty or parts.empty:
            continue
        t, s = total.iloc[0], parts.sum()
        out.append(dict(check="classes", year=y, quarter=q, table_key="gross_premium_by_class", item=c,
                        expected=t, actual=round(s, 2), passed=int(abs(t - s) <= tol(t))))
    return out


def check_ytd(panel):
    out, flags = [], []
    p = panel[(panel.table_kind == "flow") & (panel.line_key == "gross_premium")].sort_values(
        ["company_id", "table_key", "year", "quarter"])
    for (c, t, y), g in p.groupby(["company_id", "table_key", "year"]):
        prev = None
        for _, r in g.iterrows():
            if prev is not None and r["quarter"] == prev["quarter"] + 1:
                ok = r["value"] >= prev["value"] * 0.95 - 1
                out.append(dict(check="ytd", year=y, quarter=r["quarter"], table_key=t, item=c,
                                expected=prev["value"], actual=r["value"], passed=int(ok)))
                if not ok:
                    flags.append(dict(company_id=c, year=y, quarter=r["quarter"], table_key=t, flag="ytd_falls",
                                      detail=f"YTD gross premium {r['value']:,.0f} below previous quarter {prev['value']:,.0f}",
                                      treatment="excluded from single-quarter market totals"))
            prev = r
    return out, flags


def main(strict=False):
    long = pd.read_csv(os.path.join(PROCESSED, "life_long.csv"))
    totals = pd.read_csv(os.path.join(PROCESSED, "life_printed_totals.csv"))
    panel = pd.read_csv(os.path.join(PROCESSED, "life_panel.csv"), keep_default_na=False, na_values=[""])
    unmapped = pd.read_csv(os.path.join(VALIDATION, "unmapped_names.csv"))
    inv = pd.read_csv(os.path.join(VALIDATION, "sheet_inventory.csv"))

    checks = [dict(check="names", year="", quarter="", table_key="", item=n, expected="", actual="", passed=0)
              for n in unmapped["raw_name"]]
    checks += check_totals(long, totals)
    checks += check_classes(panel)
    ytd, flags = check_ytd(panel)
    checks += ytd
    ch = pd.DataFrame(checks)
    ch.to_csv(os.path.join(VALIDATION, "checks.csv"), index=False)
    pd.DataFrame(flags, columns=["company_id", "year", "quarter", "table_key", "flag", "detail", "treatment"]).to_csv(
        os.path.join(VALIDATION, "quality_flags.csv"), index=False)

    life = inv[inv.life == 1]
    cov = life.pivot_table(index="table_key", columns=life.year.astype(str) + " Q" + life.quarter.astype(str),
                           values="rows_read", aggfunc="max", fill_value=0)
    lines = ["# Validation summary", "",
             f"Workbooks read: {inv[['year','quarter']].drop_duplicates().shape[0]}  ",
             f"Life sheets read: {len(life)}; not understood: {(life.layout == 'not_understood').sum()}  ",
             f"Company names printed: {long.raw_name.nunique()}; unmapped: {len(unmapped)}", "",
             "| Check | Passed | Total |", "|---|---|---|"]
    for name, g in ch.groupby("check") if not ch.empty else []:
        lines.append(f"| {name} | {int(g.passed.sum()):,} | {len(g):,} |")
    lines += ["", f"Quality flags raised: {len(flags)} (see quality_flags.csv)", "",
              "## Tables found per quarter (rows read)", "", cov.to_markdown() if not cov.empty else "none"]
    fails = ch[(ch.passed == 0) & (ch.check == "totals")] if not ch.empty else ch
    if len(fails):
        lines += ["", "## Totals that do not reconcile", "",
                  "Each needs a note in docs/known_issues.md once explained (an IRA printing error, a missing row, and so on).", "",
                  fails.head(200).to_markdown(index=False)]
    with open(os.path.join(VALIDATION, "SUMMARY.md"), "w") as f:
        f.write("\n".join(lines) + "\n")
    print("\n".join(lines[:12]))
    hard = len(unmapped) > 0 or long.empty
    if strict:
        hard = hard or (not ch.empty and (ch.passed == 0).any())
    return 1 if hard else 0


if __name__ == "__main__":
    sys.exit(main(strict="--strict" in sys.argv))
