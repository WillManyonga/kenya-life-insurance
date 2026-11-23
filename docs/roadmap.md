# Roadmap

1. **First real run.** Let the scheduled workflow download IRA's files. Then clear the unmapped names and table titles it reports, and confirm each corporate event's effective quarter against `validation/name_timeline.csv`. Pay particular attention to the 2021 OMLAC/UAP Life transfer, the date OMLAC stops reporting, the Madison demerger quarter and the Jubilee composite split.
2. **2015–2016 from the annual reports.** IRA published no company-level workbooks before Q4 2016. The 2015 and 2016 annual reports (PDF, text layer) carry life premium and results by company. Add `src/kli/extract_annual_pdf.py` to read those tables with pdfplumber, writing to the same long format with `quarter=4` and `source_kind=annual_report`.
3. **IFRS 17 break (from Q1 2024).** Check whether IRA still prints gross premium for life companies after the switch. If only insurance revenue is printed, add a documented series break and show it on the charts.
4. **Claims settlement (long-term).** IRA's quarterly claims statistics include a long-term column. Add them as a second panel.
5. **Capital adequacy and investments**, if the life balance-sheet sheets prove consistent enough.
