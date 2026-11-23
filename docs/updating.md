# Updating and fixing the data

## A new quarter

Nothing to do. The scheduled refresh finds it. If IRA used an unusual web address the probe
missed, add one line to `config/sources.csv`:

```
quarterly_statistics,2026,2,xlsx,quarterly/2026/IRA_2026_Q2_Industry_Statistics.xlsx,https://www.ira.go.ke/lib.html?f=<slug>,added by hand
```

Then run **Actions → Refresh IRA data → Run workflow**.

## "Unmapped names" issue

IRA printed a company name that no pattern matches. Open `validation/unmapped_names.csv`, then:

- **New spelling of a known company:** widen its pattern in `reference/name_patterns.csv`.
- **New company:** add it to `reference/life_companies.csv` (give it its own `stream_id`), add a pattern, and add a `new_licence` row to `reference/corporate_events.csv` with a source link.
- **Rename:** add the new spelling to the existing company's pattern and record a `rename` event.
- **Merger or portfolio transfer:** give both companies the same `stream_id` in `life_companies.csv` and add a `merger` or `portfolio_transfer` event with the effective date. The quarter of that date is flagged `absorption_quarter` so the jump is not read as growth.

Patterns are regular expressions matched in `order` against the upper-cased name; the first match
wins, so put the more specific pattern first (see the two Old Mutual lines).

## A table the reader did not understand

`validation/sheet_inventory.csv` lists every sheet, its title and whether it was read. If a life
table shows `not_understood`, or its title landed under `other:...`, add a row to
`reference/table_map.csv`. If a column did not map to a standard line (premium, profit, a class of
business), add a row to `reference/line_map.csv`.

## Totals that do not reconcile

`validation/SUMMARY.md` lists every company-sum that misses IRA's printed total. Once you know why
(a company missing from IRA's total, a stale total, a figure filed in the wrong column), add a note to
`docs/known_issues.md`. Returns that cannot be right, such as a year-to-date premium that falls, are
listed in `validation/quality_flags.csv` and left out of single-quarter market totals.

## Exchange rates

`config/fx_kes_usd.csv` holds annual average KES per US$. Add each new year from the Central Bank
of Kenya.
