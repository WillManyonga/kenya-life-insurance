"""Shared paths, reference tables and helpers for the Kenya life-insurance pipeline."""
import csv
import fnmatch
import gzip
import hashlib
import os
import re

CODE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
# KLI_ROOT lets the tests build into a scratch folder; reference tables always come from the repo.
ROOT = os.environ.get("KLI_ROOT", CODE_ROOT)
RAW = os.path.join(ROOT, "data", "raw")
PROCESSED = os.path.join(ROOT, "data", "processed")
REF = os.path.join(CODE_ROOT, "reference")
CONFIG = os.path.join(CODE_ROOT, "config")
VALIDATION = os.path.join(ROOT, "validation")
SITE = os.path.join(ROOT, "site")
for _d in (RAW, PROCESSED, VALIDATION, os.path.join(SITE, "data")):
    os.makedirs(_d, exist_ok=True)

QUARTER_END = {1: "03-31", 2: "06-30", 3: "09-30", 4: "12-31"}


def norm(s):
    """Collapse whitespace and Excel line-break artefacts."""
    return re.sub(r"\s+", " ", str(s).replace("_x000D_", " ")).strip()


def norm_name(s):
    """Upper-case company name with punctuation reduced, for pattern matching."""
    s = norm(s).upper().replace("&", " AND ")
    s = re.sub(r"[^A-Z0-9 .\-]", " ", s)
    s = re.sub(r"\b(LIMITED|LTD|PLC)\b\.?", " ", s)
    return re.sub(r"\s+", " ", s).strip(" .-")


def slug(s, n=60):
    return re.sub(r"[^a-z0-9]+", "_", norm(s).lower()).strip("_")[:n]


def read_csv(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def write_csv(path, rows, fields=None):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fields = fields or (list(rows[0].keys()) if rows else [])
    opener = gzip.open if path.endswith(".gz") else open
    with opener(path, "wt", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def num(v):
    """Parse an IRA cell into a float. Blank or dash -> None; '(123)' -> -123."""
    if v is None:
        return None
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip().replace(",", "")
    if s in ("", "-", "--", "n/a", "N/A", "NIL", "nil"):
        return None
    neg = s.startswith("(") and s.endswith(")")
    s = s.strip("()")
    try:
        x = float(s)
    except ValueError:
        return None
    return -x if neg else x


class Ordered:
    """A list of (compiled regex, row) tried in `order`; first match wins."""

    def __init__(self, rows, field):
        rows = sorted(rows, key=lambda r: int(r["order"]))
        self.items = [(re.compile(r[field], re.I), r) for r in rows]

    def match(self, text, **filters):
        for rx, row in self.items:
            if any(not fnmatch.fnmatch(v, row.get(k) or "*") for k, v in filters.items()):
                continue
            if rx.search(text):
                return row
        return None


def load_refs():
    companies = {r["company_id"]: r for r in read_csv(os.path.join(REF, "life_companies.csv"))}
    names = Ordered(read_csv(os.path.join(REF, "name_patterns.csv")), "pattern")
    tables = Ordered(read_csv(os.path.join(REF, "table_map.csv")), "title_pattern")
    lines = Ordered(read_csv(os.path.join(REF, "line_map.csv")), "line_pattern")
    events = read_csv(os.path.join(REF, "corporate_events.csv"))
    return companies, names, tables, lines, events


def period_end(year, q):
    return f"{year}-{QUARTER_END[int(q)]}"
