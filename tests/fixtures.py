"""Small synthetic IRA-style workbooks for testing the pipeline without IRA's files.

They imitate the awkward parts of the real ones: a title row above the header, a merged
parent header, an INSURERS / REINSURERS split, printed TOTAL rows, a company renamed between
quarters, a sheet printed with companies across the columns, and general-business sheets
that must be ignored.
"""
import os

import openpyxl

Q = {
    # year, quarter: {name: (ordinary, group, deposit_admin)}  in KSh '000, year to date
    (2021, 3): {"UAP LIFE ASSURANCE LIMITED": (300, 200, 100), "BARCLAYS LIFE ASSURANCE KENYA": (50, 40, 10),
                "BRITAM LIFE ASSURANCE COMPANY (K) LIMITED": (900, 600, 1500)},
    (2021, 4): {"OLD MUTUAL LIFE ASSURANCE KENYA LIMITED": (420, 260, 150), "ABSA LIFE ASSURANCE KENYA": (70, 55, 15),
                "BRITAM LIFE ASSURANCE COMPANY (K) LIMITED": (1250, 800, 2000)},
}
REINS = {(2021, 3): ("KENYA REINSURANCE CORPORATION", 80), (2021, 4): ("KENYA REINSURANCE CORPORATION", 110)}
PBT = {(2021, 3): {"UAP LIFE ASSURANCE LIMITED": 30, "BARCLAYS LIFE ASSURANCE KENYA": -5, "BRITAM LIFE ASSURANCE COMPANY (K) LIMITED": 120},
       (2021, 4): {"OLD MUTUAL LIFE ASSURANCE KENYA LIMITED": 45, "ABSA LIFE ASSURANCE KENYA": 8, "BRITAM LIFE ASSURANCE COMPANY (K) LIMITED": 160}}


def build(raw_dir):
    for (y, q), comps in Q.items():
        wb = openpyxl.Workbook()
        g = wb.active
        g.title = "GEN1"
        g.append(["APPENDIX 1: GENERAL INSURANCE BUSINESS REVENUE ACCOUNT"])
        g.append(["Company", "Gross premium"])
        g.append(["SOME GENERAL INSURER", 999])

        ws = wb.create_sheet("LT3")
        ws.append([f"APPENDIX 3: GROSS PREMIUM INCOME UNDER LONG TERM INSURANCE BUSINESS AS AT {q}Q {y} (KSHS '000)"])
        ws.append([None, None, "Individual", None, "Group", None])
        ws.append([None, "Company", "Ordinary Life", "Group Life", "Deposit Administration", "Total"])
        ws.append([None, "INSURERS"])
        for n, (a, b, c) in comps.items():
            ws.append([None, n, a, b, c, a + b + c])
        tot = [sum(v[i] for v in comps.values()) for i in range(3)]
        ws.append([None, "TOTAL", *tot, sum(tot)])
        ws.append([None, "REINSURERS"])
        rn, rv = REINS[(y, q)]
        ws.append([None, rn, 0, rv, 0, rv])
        ws.append([None, "TOTAL", 0, rv, 0, rv])
        ws.append([None, "INDUSTRY TOTAL", tot[0], tot[1] + rv, tot[2], sum(tot) + rv])

        pl = wb.create_sheet("LT9")
        pl.append([f"APPENDIX 9: LONG TERM INSURANCE BUSINESS PROFIT AND LOSS ACCOUNT {y} Q{q}"])
        pl.append(["Item", *PBT[(y, q)].keys(), "TOTAL"])
        pl.append(["Profit before tax", *PBT[(y, q)].values(), sum(PBT[(y, q)].values())])
        pl.append(["Taxation", *[-1] * len(PBT[(y, q)]), -len(PBT[(y, q)])])

        d = os.path.join(raw_dir, "quarterly", str(y))
        os.makedirs(d, exist_ok=True)
        wb.save(os.path.join(d, f"IRA_{y}_Q{q}_Industry_Statistics.xlsx"))
