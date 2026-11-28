"""Download IRA source files listed in config/sources.csv, and look for newly published quarters.

    python -m kli.download            # fetch anything missing, then probe for new quarters
    python -m kli.download --no-probe # fetch only what is listed

Every file is checked by its first bytes (an Excel workbook is a zip and starts with PK;
a PDF starts with %PDF), so an IRA error page saved as .xlsx is caught here, not later.
data/raw/manifest.csv records the SHA-256 of every file used, so any rebuild can be
traced to the exact bytes.
"""
import argparse
import datetime as dt
import os
import sys
import time

import requests

from .common import CONFIG, RAW, read_csv, sha256, write_csv

SOURCES = os.path.join(CONFIG, "sources.csv")
MANIFEST = os.path.join(RAW, "manifest.csv")
UA = {"User-Agent": "Mozilla/5.0 (kenya-life-insurance data pipeline; +https://github.com)"}
BASE = "https://www.ira.go.ke/lib.html?f="
# Slugs IRA has used for its quarterly statistics workbooks, newest style first.
SLUGS = ["quarter-{q}-{y}-industry-statistics", "quarter-{q}-{y}-statistics", "q{q}-{y}-statistics",
         "quarter{q}-{y}-statistics", "quarter-{q}-{y}-insurance-industry-statistics"]
# Slugs IRA has used for its claims settlement statistics workbooks.
CLAIM_SLUGS = ["quarter-{q}-{y}-claims-settlement-statistics", "q{q}{y}-claims-statistics", "quarter{q}-{y}-claims-statistics",
               "quarter-{q}-{y}-claims-statistics"]
MAGIC = {"xlsx": b"PK", "xlsm": b"PK", "xls": b"\xd0\xcf", "pdf": b"%PDF"}


LAST = {}   # url -> what came back, for validation/download_failures.csv


def fetch(url, timeout=120):
    for attempt in range(3):
        try:
            r = requests.get(url, headers=UA, timeout=timeout)
            LAST[url] = f"HTTP {r.status_code}, {r.headers.get('content-type', '')}, {len(r.content)} bytes, starts {r.content[:40]!r}"
            if r.status_code == 200:
                return r.content
            if r.status_code == 404:
                return None
        except requests.RequestException as e:
            LAST[url] = f"error {type(e).__name__}: {str(e)[:120]}"
        time.sleep(3 * (attempt + 1))
    return None


def looks_like(content, ext):
    return bool(content) and content.startswith(MAGIC.get(ext, b""))


FAIL = []


def download_listed(sources):
    got, failed = 0, []
    for s in sources:
        path = os.path.join(RAW, s["save_as"])
        if os.path.exists(path):
            continue
        content = fetch(s["url"])
        if not looks_like(content, s["ext"]):
            failed.append(s["save_as"])
            FAIL.append(dict(file=s["save_as"], url=s["url"], got=LAST.get(s["url"], "")))
            continue
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            f.write(content)
        got += 1
    return got, failed


def next_quarters(sources, horizon=4):
    stats = [(int(s["year"]), int(s["quarter"])) for s in sources if s["kind"] == "quarterly_statistics"]
    y, q = max(stats)
    today = dt.date.today()
    out = []
    for _ in range(horizon):
        q += 1
        if q == 5:
            y, q = y + 1, 1
        if dt.date(y, [3, 6, 9, 12][q - 1], 28) > today:
            break
        out.append((y, q))
    return out


def probe_claims(sources):
    """The next claims settlement quarters after the last one listed."""
    have = [(int(s["year"]), int(s["quarter"])) for s in sources if s["kind"] == "claims_statistics"]
    if not have:
        return []
    y, q = max(have)
    added = []
    for _ in range(3):
        q += 1
        if q == 5:
            y, q = y + 1, 1
        if dt.date(y, [3, 6, 9, 12][q - 1], 28) > dt.date.today():
            break
        for pat in CLAIM_SLUGS:
            url = BASE + pat.format(q=q, y=y)
            content = fetch(url, timeout=60)
            if looks_like(content, "xlsx"):
                row = dict(kind="claims_statistics", year=y, quarter=q, ext="xlsx",
                           save_as=f"claims/{y}/IRA_{y}_Q{q}_Claims_Statistics.xlsx", url=url, note=f"found by probe {dt.date.today()}")
                path = os.path.join(RAW, row["save_as"])
                os.makedirs(os.path.dirname(path), exist_ok=True)
                with open(path, "wb") as f:
                    f.write(content)
                added.append(row)
                break
        else:
            break
    return added


def probe(sources):
    added = []
    for y, q in next_quarters(sources):
        for pat in SLUGS:
            url = BASE + pat.format(q=q, y=y)
            content = fetch(url, timeout=60)
            if looks_like(content, "xlsx"):
                row = dict(kind="quarterly_statistics", year=y, quarter=q, ext="xlsx",
                           save_as=f"quarterly/{y}/IRA_{y}_Q{q}_Industry_Statistics.xlsx", url=url,
                           note=f"found by probe {dt.date.today()}")
                path = os.path.join(RAW, row["save_as"])
                os.makedirs(os.path.dirname(path), exist_ok=True)
                with open(path, "wb") as f:
                    f.write(content)
                added.append(row)
                break
    return added


def write_manifest(sources):
    rows = []
    for s in sources:
        path = os.path.join(RAW, s["save_as"])
        ok = os.path.exists(path)
        rows.append(dict(kind=s["kind"], year=s["year"], quarter=s["quarter"], path=s["save_as"],
                         status="ok" if ok else "missing", bytes=os.path.getsize(path) if ok else "",
                         sha256=sha256(path) if ok else "", url=s["url"]))
    write_csv(MANIFEST, rows)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-probe", action="store_true")
    ap.add_argument("--kinds", default="quarterly_statistics,annual_report,annual_statistics,quarterly_release,claims_statistics,registry")
    a = ap.parse_args(argv)
    sources = read_csv(SOURCES)
    kinds = set(a.kinds.split(","))
    got, failed = download_listed([s for s in sources if s["kind"] in kinds])
    print(f"downloaded {got}; could not fetch {len(failed)}")
    for f in failed:
        print("  missing:", f)
    if not a.no_probe:
        added = probe(sources) + probe_claims(sources)
        if added:
            sources += added
            write_csv(SOURCES, sources)
            print("new quarters found:", ", ".join(f"{r['year']} Q{r['quarter']}" for r in added))
        else:
            print("no new quarter published yet")
    write_manifest(sources)
    write_csv(os.path.join(os.path.dirname(RAW), "..", "validation", "download_failures.csv"), FAIL, ["file", "url", "got"])
    # Missing files are reported, not fatal: IRA links break and some periods were never published.
    return 0


if __name__ == "__main__":
    sys.exit(main())
