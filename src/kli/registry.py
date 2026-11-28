"""Registered insurers by year, from IRA's own lists.

Sources, all IRA's:
  - the annual report's appendix "Directory of (regulated) insurance and reinsurance companies in
    Kenya" (reports for 2015 to 2024; there was no 2019 report): one row per company with its type;
  - reference/registry_manual.csv: years whose directory IRA printed as a picture (2023), read once by
    OCR, checked by hand against the neighbouring years and IRA's printed count, and kept here;
  - the licence lists IRA publishes under section 184 of the Insurance Act (data/raw/registry/, 2025
    and 2026): one table per type, with the classes of business each company may write;
  - the annual reports' table "Number of licensed/registered insurers", kept as a check.

Every type is extracted (long-term, general, composite, reinsurer, microinsurer). What is written to
the repository is limited by config/scope.csv: life only for now (long-term and composite companies,
since composites write life business). Set general or reinsurer to yes there to publish the rest.

Writes:
  data/processed/registered_insurers.csv  year, source, name, type, segment, classes, company_id
  validation/registry_counts.csv          companies found per year and type, against IRA's printed count
"""
import collections
import glob
import html
import os
import re
import subprocess
import sys

from .common import CONFIG, PROCESSED, RAW, REF as REFERENCE, VALIDATION, load_refs, norm_name, read_csv, write_csv

TYPES = [  # printed type -> standard type; the first match wins
    (r"liai?son", "liaison_office"), (r"re-?\s*insur", "reinsurer"), (r"micro", "microinsurer"),
    (r"composite", "composite"), (r"long[\s_-]*term|^life", "long_term"), (r"general", "general")]
SEGMENT = {"long_term": "life", "composite": "life", "general": "general", "microinsurer": "general",
           "reinsurer": "reinsurer", "liaison_office": "reinsurer"}
TYPE_WORD = re.compile(r"^\(?(general|long|longterm|long-term|term|composite|reinsurance|re-insurance|reinsurer|micro|"
                       r"microinsurance|micro-insurance|microinsurer|life|liaison|liason|office)\)?$", re.I)


def std_type(s):
    t = (s or "").lower()
    for rx, k in TYPES:
        if re.search(rx, t):
            return k
    return ""


def scope(dataset):
    """Segments to publish for a dataset, from config/scope.csv (dataset,segment,publish)."""
    p = os.path.join(CONFIG, "scope.csv")
    rows = read_csv(p) if os.path.exists(p) else []
    out = {r["segment"] for r in rows if r["dataset"] in (dataset, "all") and r["publish"].strip().lower() in ("1", "yes", "true")}
    return out or {"life"}


def page_texts(path, layout=True):
    t = subprocess.run(["pdftotext"] + (["-layout"] if layout else []) + [path, "-"], capture_output=True, text=True).stdout
    return t.split("\f")


def page_words(path, page_no):
    """Words with their boxes for one page (1-based), from pdftotext -bbox. Poppler reads the
    directory pages whose glyphs are stored one by one or rotated, which pdfplumber does not."""
    out = subprocess.run(["pdftotext", "-bbox", "-f", str(page_no), "-l", str(page_no), path, "-"],
                         capture_output=True, text=True).stdout
    words = []
    for m in re.finditer(r'<word xMin="([\d.]+)" yMin="([\d.]+)" xMax="([\d.]+)" yMax="([\d.]+)">(.*?)</word>', out):
        x0, y0, x1, y1, t = m.groups()
        words.append(dict(x0=float(x0), top=float(y0), x1=float(x1), bottom=float(y1), text=html.unescape(t)))
    return words


# ---------------------------------------------------------------- annual report directories
def is_directory(t):
    return bool(re.search(r"directory of (regulated )?(insurance|insurers)", t, re.I) and re.search(r"P\.?\s?O\.?\s*Box", t, re.I)
                and not re.search(r"directory of (insurance groups|other)", t, re.I))


def parse_words(words):
    """Columns are found from the page itself: serial numbers at the left, the postal address column
    (first "P.O" or the "Postal" heading), and the type column (where type words start). A company's
    name may wrap onto the lines above and below its serial; each word goes to the nearest serial."""
    pob = [w for w in words if re.match(r"p\.?o\.?$", w["text"], re.I)]
    postal = [w for w in words if re.match(r"postal", w["text"], re.I)]
    xs = [w["x0"] for w in pob] + [w["x0"] for w in postal]
    if not xs:
        return []
    xp = sorted(xs)[len(xs) // 4] - 3
    left = [w for w in words if w["x1"] <= xp + 1]
    nums = [w for w in left if re.fullmatch(r"\d{1,2}", w["text"])]
    if not nums:
        return []
    xmin = min(w["x0"] for w in nums)
    serials = sorted([w for w in nums if w["x0"] < xmin + 12], key=lambda w: w["top"])
    sx = max(w["x1"] for w in serials)
    first = serials[0]["top"]
    typ_words = [w for w in left if w["x0"] > sx + 0.4 * (xp - sx) and TYPE_WORD.match(w["text"]) and std_type(w["text"])]
    xt = sorted(w["x0"] for w in typ_words)[len(typ_words) // 10] if typ_words else xp
    head = max([w["bottom"] for w in words if re.match(r"(postal|telephone|address|e-?mail)$", w["text"], re.I)
                and first - 60 < w["top"] and w["bottom"] < first - 2] or [0])
    head = min(head, first - 14)   # a wrapped first name can start above its serial
    banner = [w["top"] for w in words if re.match(r"(continued|appendix|directory|previous)", w["text"], re.I)]
    body = [w for w in left if w["x0"] > sx + 1 and w["top"] > head + 1 and not any(abs(w["top"] - b) < 2.5 for b in banner)]
    centers = [(s["top"] + s["bottom"]) / 2 for s in serials]

    def blocks(ws):
        """Lines of words, then blocks of lines separated by a gap wider than a line: one block is
        one company's cell. Each block goes to the serial nearest its middle."""
        lines = []
        for w in sorted(ws, key=lambda w: w["top"]):
            if lines and abs(lines[-1][0]["top"] - w["top"]) < 3:
                lines[-1].append(w)
            else:
                lines.append([w])
        out, cur = [], []
        for ln in lines:
            if cur and ln[0]["top"] - cur[-1][0]["bottom"] > 5:
                out.append(cur)
                cur = []
            cur.append(ln)
        if cur:
            out.append(cur)
        got = collections.defaultdict(list)
        txt = lambda ln: " ".join(w["text"] for w in sorted(ln, key=lambda w: w["x0"]))
        for bl in out:
            top, bot = bl[0][0]["top"], max(w["bottom"] for w in bl[-1])
            inside = [i for i, c in enumerate(centers) if top - 2 <= c <= bot + 2]
            if len(inside) > 1:   # two rows printed with no gap between them: line by line
                for ln in bl:
                    m = (ln[0]["top"] + ln[0]["bottom"]) / 2
                    got[min(inside, key=lambda i: abs(centers[i] - m))].append(txt(ln))
                continue
            mid = (top + bot) / 2
            k = min(range(len(centers)), key=lambda i: abs(centers[i] - mid))
            got[k] += [txt(ln) for ln in bl]
        return got

    names = blocks([w for w in body if w["x1"] <= xt - 1])
    types = blocks([w for w in body if w["x0"] >= xt - 2])
    rows = []
    for k, s in enumerate(serials):
        name = re.sub(r"\s+", " ", " ".join(names.get(k, []))).strip()
        name = re.sub(r"BACK<<|NEXT>>", "", name).strip()
        name = re.sub(r"\b(Limited|Ltd)\.?\s+[A-Z][a-z].*$", r"\1", name)   # a neighbour's name run on after "Limited"
        if name:
            rows.append(dict(serial=int(s["text"]), name=name, type_raw=" ".join(types.get(k, [])).strip()))
    return rows


def annual_directories():
    out = []
    for path in sorted(glob.glob(os.path.join(RAW, "annual", "IRA_Annual_Report_*.pdf"))):
        year = int(re.search(r"(\d{4})", os.path.basename(path)).group(1))
        seen = set()
        for i, t in enumerate(page_texts(path)):
            if not is_directory(t):
                continue
            for r in parse_words(page_words(path, i + 1)):
                if (r["serial"], r["name"]) in seen:   # IRA sometimes prints a serial twice (51 in 2020)
                    continue
                seen.add((r["serial"], r["name"]))
                out.append(dict(year=year, source=f"IRA annual report {year}, directory of insurance and reinsurance companies", **r))
    return out


PRINTED_ROW = [(r"general insur", "general"), (r"long\s*term insur", "long_term"), (r"composite", "composite"),
               (r"reinsur", "reinsurer"), (r"micro", "microinsurer")]


def printed_counts():
    """IRA's table of the number of licensed insurers, by year and type (each report prints the year
    and usually the year before)."""
    out = {}
    for path in sorted(glob.glob(os.path.join(RAW, "annual", "IRA_Annual_Report_*.pdf"))):
        year = int(re.search(r"(\d{4})", os.path.basename(path)).group(1))
        lines = "\n".join(page_texts(path)).splitlines()
        starts = [i for i, ln in enumerate(lines) if re.search(r"table \d+: number of (licensed|registered) insurers", ln, re.I)
                  and any(re.search(r"type of business|regulated entity|number (of|licensed)", x, re.I) for x in lines[i + 1:i + 6])]
        for s in starts[:1]:
            years = None
            for ln in lines[s + 1:s + 16]:
                if re.match(r"\s*total\b", ln, re.I):
                    break
                if re.search(r"table \d+", ln, re.I):
                    continue
                ys = re.findall(r"\b(20\d\d)\b", ln)
                if len(ys) >= 1 and not re.search(r"insur", ln, re.I):
                    years = [int(y) for y in ys]
                    continue
                for rx, k in PRINTED_ROW:
                    if re.search(rx, ln, re.I) and not re.search(r"registration", ln, re.I):
                        nums = [int(n) for n in re.findall(r"(?<![\d.])(\d{1,3})(?![\d.])", ln)]
                        nums = nums[-len(years):] if years and len(nums) >= len(years) else nums[-1:]
                        ys = years if years and len(nums) == len(years) else [year]
                        for y, n in zip(ys, nums):
                            if y == year:
                                out[(y, k)] = n      # a report's own year wins over the next report's comparison column
                            else:
                                out.setdefault((y, k), n)
                        break
    return out


# ---------------------------------------------------------------- section 184 licence lists
SECTION = [(r"\bre-?insur(ers?|ance companies)\b", "reinsurer"), (r"micro\s*-?\s*insur", "microinsurer"),
           (r"general insur", "general"), (r"long[\s-]*term|life\)? insur", "long_term"),
           (r"composite insur", "composite")]
STOP = re.compile(r"brokers|investigators|assessors|adjusters|medical insurance providers|risk managers|"
                  r"surveyors|claims settling|bancassurance|agents", re.I)


COMPANY = re.compile(r"\b(limited|ltd|company|insurance|assurance|reinsurance|microinsurance|mutual|corporation|plc)\b", re.I)
INTERMEDIARY = re.compile(r"brokers?|agenc|assessors?|adjusters?|investigat|surveyors?|consultants?|risk manag|bancassurance", re.I)
HEAD_WORD = re.compile(r"^(serial|no\.?|authori[sz]ed|classes?|of|insurance|business|companies|insurers?)$", re.I)
CLASS_TOKEN = re.compile(r"^(\d{2}[a-z]?[,&]?)+$|^[\d,&\-–]+$")


def licence_page(words):
    """One page of a licence list, which IRA sets in two columns of tables. Returns
    [(column x, top, kind, payload)] in reading order: kind 'head' (a table heading) or 'row'."""
    lines = {}
    for w in words:
        lines.setdefault(round(w["top"] / 2.5), []).append(w)
    serials = []
    for ws in lines.values():
        ws.sort(key=lambda w: w["x0"])
        for i, w in enumerate(ws[:-1]):
            nxt = ws[i + 1]
            if re.fullmatch(r"\d{1,2}\.?", w["text"]) and nxt["x0"] - w["x1"] < 60 and re.match(r"[A-Z(]", nxt["text"]) \
                    and not CLASS_TOKEN.match(nxt["text"]):
                serials.append(w)
    if not serials:
        return []
    xs = sorted(round(w["x0"]) for w in serials)
    groups = [[xs[0]]]
    for x in xs[1:]:
        if x - groups[-1][-1] > 40:
            groups.append([x])
        else:
            groups[-1].append(x)
    cols = [g[0] for g in groups if len(g) >= 3]   # a real column has several serial numbers
    if not cols:
        return []
    serials = [w for w in serials if any(abs(round(w["x0"]) - c) <= 40 for c in cols)]
    bounds = [(c - 8, (cols[i + 1] - 8) if i + 1 < len(cols) else 1e9) for i, c in enumerate(cols)]
    out = []
    for lo, hi in bounds:
        cw = [w for w in words if lo <= w["x0"] < hi]
        key = min([w["top"] for w in cw if re.fullmatch(r"KEY:?", w["text"])] or [1e9])
        cw = [w for w in cw if w["top"] < key - 1]
        heads = []
        for t in sorted({round(w["top"] / 2.5) for w in cw}):
            ln = [w for w in cw if round(w["top"] / 2.5) == t]
            txt = " ".join(w["text"] for w in sorted(ln, key=lambda w: w["x0"]))
            caps = " ".join(w["text"] for w in sorted(ln, key=lambda w: w["x0"]) if w["text"].upper() == w["text"] and re.search(r"[A-Z]{3}", w["text"]))
            kind = "stop" if STOP.search(caps) else next((k for rx, k in SECTION if re.search(rx, caps, re.I)), None)
            if kind and not re.search(r"\d{2},", txt):
                heads.append((min(w["top"] for w in ln), kind))
        ss = sorted([w for w in serials if lo <= w["x0"] < hi and w["top"] < key - 1], key=lambda w: w["top"])
        stops = sorted([h[0] for h in heads] + [key])
        for h in heads:
            out.append((lo, h[0], "head", h[1]))
        for i, sw in enumerate(ss):
            nxt = ss[i + 1]["top"] - 1 if i + 1 < len(ss) else 1e9
            nxt = min([nxt] + [t - 1 for t in stops if t > sw["top"] + 1])
            band = [w for w in cw if sw["top"] - 3 <= w["top"] < nxt and w["x0"] > sw["x1"] + 1]
            name = [w for w in band if not CLASS_TOKEN.match(w["text"]) and not (w["top"] < sw["top"] - 1)]
            cls = [w for w in band if CLASS_TOKEN.match(w["text"])]
            if cls:   # the classes column starts at the first class number on the serial's line
                cx = min(w["x0"] for w in cls)
                name = [w for w in name if w["x0"] < cx - 2]
            order = lambda ws: " ".join(w["text"] for w in sorted(ws, key=lambda w: (round(w["top"] / 2.5), w["x0"])))
            nm = re.sub(r"\s+", " ", order(name)).strip()
            if nm:
                out.append((lo, sw["top"], "row", dict(serial=int(sw["text"].rstrip(".")), name=nm,
                                                       classes=re.sub(r"\s+", " ", order(cls)).strip(" ,"))))
    return sorted(out, key=lambda r: (r[0], r[1], r[2] != "head"))


def licence_lists():
    out = []
    for path in sorted(glob.glob(os.path.join(RAW, "registry", "*.pdf"))):
        year = int(re.search(r"(20\d\d)", os.path.basename(path)).group(1))
        texts = page_texts(path)
        npages = len(texts)
        section, seen = "", set()
        for p in range(1, npages + 1):
            for _, _, kind, payload in licence_page(page_words(path, p)):
                if kind == "head":
                    section = "" if payload == "stop" else payload
                    continue
                if not section or not COMPANY.search(payload["name"]) or INTERMEDIARY.search(payload["name"]):
                    continue
                k = (section, payload["serial"], payload["name"])
                if k in seen:
                    continue
                seen.add(k)
                out.append(dict(year=year, source=f"IRA licence list {year} (Insurance Act s.184)", type_raw=section, **payload))
            # the insurers' tables end with the key to the classes of business; intermediaries follow
            if re.search(r"\bKEY\b", texts[p - 1]):
                break
    # a company licensed for both general and long-term business is a composite
    both = collections.defaultdict(set)
    for r in out:
        both[(r["year"], norm_name(r["name"]))].add(r["type_raw"])
    for r in out:
        if r["type_raw"] == "long_term" and "general" in both[(r["year"], norm_name(r["name"]))]:
            r["type_raw"] = "composite (long term and general)"
    return out


def manual():
    p = os.path.join(REFERENCE, "registry_manual.csv")
    return [dict(r, year=int(r["year"]), serial=int(r["serial"] or 0)) for r in read_csv(p)] if os.path.exists(p) else []


def main():
    companies, names, _, _, _ = load_refs()
    rows = annual_directories()
    done = {r["year"] for r in rows}
    rows += [r for r in manual() if r["year"] not in done]
    lic = licence_lists()
    rows += [r for r in lic if r["year"] not in done]
    by_name = {}
    for r in rows:
        r["name"] = re.sub(r"Asssurance", "Assurance", r["name"])
        r["type"] = std_type(r.get("type_raw", ""))
        if r["type"]:
            by_name.setdefault(norm_name(r["name"]), r["type"])
    for r in rows:   # a type the page did not print next to the name: from the name, or the same name in another year
        if not r["type"]:
            n = r["name"].lower()
            r["type"] = "reinsurer" if "reinsurance" in n else "microinsurer" if "micro" in n else by_name.get(norm_name(r["name"]), "")
            r["type_raw"] = (r.get("type_raw") or "") + " (type inferred)"
        r["segment"] = SEGMENT.get(r["type"], "")
        cid, per = "", f"{r['year']}Q4"
        if r["segment"] == "life":   # life companies get the same ids as the rest of the repo, by the same dated rules
            for rx, row in names.items:
                lo, hi = row.get("valid_from") or "0000Q0", row.get("valid_to") or "9999Q9"
                if lo <= per <= hi and rx.search(norm_name(r["name"])):
                    cid = row["company_id"]
                    break
        r["company_id"] = cid
        r["stream_id"] = companies.get(cid, {}).get("stream_id", cid) if cid else ""
        r["classes"] = ", ".join(c for c in re.split(r"[,&\s]+", r.get("classes") or "") if c)
    keep = scope("registry")
    cols = ["year", "source", "serial", "name", "type", "segment", "classes", "company_id", "stream_id"]
    pub = sorted([r for r in rows if r["segment"] in keep], key=lambda r: (r["year"], r["name"].lower()))
    write_csv(os.path.join(PROCESSED, "registered_insurers.csv"), [{c: r.get(c, "") for c in cols} for r in pub])
    found = collections.Counter((r["year"], r["type"] or "unknown") for r in rows)
    printed = printed_counts()
    keys = sorted(set(found) | set(printed))
    write_csv(os.path.join(VALIDATION, "registry_counts.csv"),
              [dict(year=y, type=t, found=found.get((y, t), ""), printed=printed.get((y, t), ""),
                    check="" if (y, t) not in found or (y, t) not in printed else ("pass" if found[(y, t)] == printed[(y, t)] else "differs"))
               for y, t in keys])
    write_csv(os.path.join(PROCESSED, "registered_counts_printed.csv"),
              [dict(year=y, type=t, companies=n) for (y, t), n in sorted(printed.items())])
    print(f"registry: {len(rows)} rows over {len({r['year'] for r in rows})} years; {len(pub)} published ({', '.join(sorted(keep))})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
