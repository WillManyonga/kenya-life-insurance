# Known issues in IRA publications

Every validation failure that remains, and how it is treated. Figures are kept exactly as IRA
prints them; nothing is "corrected" silently.

## Printed totals that do not equal the sum of company rows (27 of 15,546 checks)

| Where | What | Treatment |
|---|---|---|
| Pensions revenue account, Q4 2016 to Q4 2019 (10 quarters) | IRA's printed TOTAL for *Total Benefits* does not equal the sum of the company rows; the other columns of the same table agree | Company rows used; total ignored |
| Long-term balance sheets, 17 cells (e.g. Q2 2022 revaluation reserves, Q1 2023 share capital) | Small differences between the printed TOTAL column and the companies on the three pages | Company figures used; balance sheets are not used in the headline views |

## Returns flagged in `validation/quality_flags.csv`

- **Year-to-date premium that falls** (164 company-quarters). These are mostly IRA printing zeros for a company that did not file in time (for example The Kenyan Alliance in Q3 2017, Q3 2025 and Q1 2026). They are left out of single-quarter market totals.
- **Profit above half of premium** (6 company-years). These are kept as printed and left out of average margins in the explorer:
  - Kenindia 2024 shows KSh 21.3bn profit before tax on KSh 14.1bn premium. This is almost certainly a filing or printing error, and it inflates IRA's 2024 market profit to KSh 42.0bn.
  - GA Life 2024–2025 shows 84% and 62% of premium under IFRS 17. This may be genuine, since investment and finance results are large under IFRS 17, but it needs confirming against GA Life's audited accounts.
  - OMLAC 2016 and 2024, Kenyan Alliance 2025: small books with volatile results.

## Breaks in the series

- **IFRS 17 from Q1 2024.** The long-term P&L changes from IFRS 4 lines (profit transferred from the revenue account, and so on) to IFRS 17 lines (insurance revenue, insurance service result). Profit before tax is printed under both regimes and is used for margins. Margins either side of 2024 are not strictly comparable.
- **Class split.** Up to 2022 IRA prints one *Pensions* class. From 2023 it prints *Personal Pensions* and *Deposit Administration* separately.
- **2017.** There is no Q4 2017 quarterly workbook. The 2017 annual statistics workbook stands in for it, and its premium table is gross *direct* premium, which excludes inward reinsurance.
- **2015 to Q3 2016.** No company-level workbooks exist. See `docs/roadmap.md`.
