# Kenya Life Insurance Data

Every Kenyan life insurer's long-term business, quarter by quarter, rebuilt from the Insurance
Regulatory Authority's (IRA) published statistics. Renamed, merged and acquired companies are kept
on one continuous line, with a dated, sourced note for every change.

The method follows Marion Peter's general-insurance work
([ira-kenya-data](https://github.com/maidenpeter/ira-kenya-data)): trace every figure to its file,
sheet and row; check company rows against IRA's printed totals; read each company across quarters;
and tie every name IRA has printed to one stable id. Peter's repository has no licence file, so
none of its code is copied here; the pipeline is written fresh for the life tables.

## What you get

| File | What it holds |
|---|---|
| `data/processed/life_consolidated.xlsx` | The consolidated file for Excel: full-year figures per company and per continuity stream, market quarterly series, name map, corporate events, quality flags |
| `data/processed/life_annual_by_stream.csv` | Full-year (Q4 year-to-date) gross premium, profit, premium mix, share and rank per continuity stream |
| `data/processed/life_annual_by_company.csv` | The same per legal reporting entity |
| `data/processed/life_panel.csv` | Every life value IRA printed, on stable company ids, with single-quarter figures and how each was derived |
| `data/processed/life_long.csv` | The raw extraction, exactly as printed, with source file, sheet and row |
| `validation/SUMMARY.md` | What was checked, what passed, and which tables were found each quarter |
| `site/index.html` | The explorer page, published to GitHub Pages |

All money is in **KSh thousands, year to date, unaudited**, as IRA publishes it.

## The explorer

The explorer is published on GitHub Pages at `https://willmanyonga.github.io/kenya-life-insurance/`.
It has:
- headline tiles for market premium, growth, number of insurers, top-5 share and market margin;
- the Deloitte *East Africa Insurance Report 2023* views, updated to any window you choose: premium CAGR against average profit margin, with bubbles sized by premium; and the top life insurers by gross premium for the last two years;
- market premium by year;
- a single-company view showing every entity in its continuity line and the corporate events, with sources.

Premium can be shown in KSh or US$. The US$ rates are in `config/fx_kes_usd.csv`, and the 2024 and 2025 rates still need filling in from the Central Bank of Kenya.

## Keeping it up to date

Nothing needs to be done by hand in a normal quarter. `.github/workflows/refresh.yml` runs on the
6th and 21st of every month. It:

1. downloads any file in `config/sources.csv` that is not yet in `data/raw/`;
2. tries IRA's usual web addresses for the next quarter and adds the workbook if it has been published;
3. rebuilds and validates every table, then commits the result;
4. republishes the explorer.

If IRA prints a company name the crosswalk does not know, or changes a layout the reader cannot
follow, the run stops and opens a GitHub issue that lists the problem. See `docs/updating.md` for
the two-minute fixes.

You can also run it locally:

```bash
pip install -r requirements.txt
./run_all.sh            # download + build
./run_all.sh --offline  # rebuild from files already in data/raw
python -m pytest -q tests
```

## Following a company through its name changes

`reference/name_patterns.csv` maps every spelling IRA prints to a company id.
`reference/life_companies.csv` groups those ids into continuity streams.
`reference/corporate_events.csv` records the dated event behind each change, with a source link.
Examples already seeded:

- Barclays Life Assurance Kenya → Absa Life Assurance Kenya (10 Feb 2020) → First Assurance Life (2026)
- UAP Life Assurance → Old Mutual Life Assurance Kenya (May 2022), which absorbs the Old Mutual Life Assurance Company closed fund
- Metropolitan Cannon Life → Cannon Life Assurance after Momentum Metropolitan's 2022 exit
- Pan Africa Life → Sanlam Life → Sanlam Allianz Life Insurance (Kenya) (Nov 2025)
- ICEA Life → ICEA LION Life Assurance; CfC Life → Liberty Life; Shield Assurance → Prudential Life

`validation/name_timeline.csv` shows every printed name with the first and last year it appears,
so each link can be checked against the data.

## Coverage

IRA's quarterly workbooks run from Q4 2016 to the latest quarter. There is no Q4 2017 workbook, so
2017 comes from the 2017 annual statistics workbook. Before Q4 2016, and for 2015 as a whole, IRA
published only PDFs: the quarterly releases and the annual reports. Reading the 2015–2016 annual
report tables is the next step (see `docs/roadmap.md`).

## Status

The pipeline has been tested end to end on synthetic IRA-style workbooks (`tests/`). It has **not
yet been run on IRA's real files**: the IRA site was unreachable from the build environment, so the
first GitHub Actions run does the first real download. Expect that first run to raise an issue with
a few unmapped names or table titles. That is the intended way to finish the mapping.
