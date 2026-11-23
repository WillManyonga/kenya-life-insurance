"""End-to-end test on synthetic workbooks: extract -> panel -> validate -> views."""
import importlib
import json
import os
import sys

import pandas as pd
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    root = tmp_path_factory.mktemp("build")
    os.environ["KLI_ROOT"] = str(root)
    import kli.common
    importlib.reload(kli.common)
    mods = []
    for m in ("extract", "panel", "validate", "views"):
        mod = importlib.import_module(f"kli.{m}")
        mods.append(importlib.reload(mod))
    from fixtures import build
    build(os.path.join(root, "data", "raw"))
    codes = [m.main() for m in mods]
    yield root, codes
    os.environ.pop("KLI_ROOT")


def read(root, *p):
    return pd.read_csv(os.path.join(root, *p))


def test_runs_clean(built):
    _, codes = built
    assert codes == [0, 0, 0, 0]


def test_general_sheets_ignored(built):
    root, _ = built
    long = read(root, "data/processed/life_long.csv.gz")
    assert "SOME GENERAL INSURER" not in set(long.raw_name)


def test_renames_join_one_company(built):
    root, _ = built
    tl = read(root, "validation/name_timeline.csv")
    ids = dict(zip(tl.raw_name, tl.company_id))
    assert ids["UAP LIFE ASSURANCE LIMITED"] == ids["OLD MUTUAL LIFE ASSURANCE KENYA LIMITED"] == "old_mutual_life_kenya"
    assert ids["BARCLAYS LIFE ASSURANCE KENYA"] == ids["ABSA LIFE ASSURANCE KENYA"] == "absa_life"
    assert read(root, "validation/unmapped_names.csv").empty


def test_single_quarter_across_rename(built):
    root, _ = built
    p = read(root, "data/processed/life_panel.csv.gz")
    r = p[(p.company_id == "old_mutual_life_kenya") & (p.line_key == "gross_premium") & (p.quarter == 4)]
    assert r.q_value.iloc[0] == (420 + 260 + 150) - (300 + 200 + 100)
    assert r.q_flag.iloc[0] == "ytd_difference"


def test_totals_and_classes_reconcile(built):
    root, _ = built
    ch = read(root, "validation/checks.csv")
    assert (ch[ch.check == "totals"].passed == 1).all()
    assert (ch[ch.check == "classes"].passed == 1).all()


def test_columnwise_profit_sheet(built):
    root, _ = built
    a = read(root, "data/processed/life_annual_by_company.csv")
    b = a[(a.company_id == "britam_life") & (a.year == 2021)].iloc[0]
    assert b.profit_kes000 == 160 and b.gross_premium_kes000 == 4050


def test_site_data(built):
    root, _ = built
    d = json.load(open(os.path.join(root, "site/data/life.json")))
    assert d["streams"]["old_mutual_life"]["years"]["2021"]["gwp"] == 830
