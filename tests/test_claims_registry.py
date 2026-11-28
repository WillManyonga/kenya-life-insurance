"""Small checks on the claims settlement and register readers."""
from kli import claims, registry


def test_claims_tables_are_classified_by_title():
    assert claims.classify("Appendix 5: Analysis of long-term insurance business claims movement (numbers) for the quarter") == ("long_term", "number")
    assert claims.classify("Appendix 6: Analysis of long-term insurance business claims movement (amount) for the quarter") == ("long_term", "amount")
    assert claims.classify("Appendix 1: Analysis of general insurance business liability claims movement (numbers)") == ("general_liability", "number")
    assert claims.classify("Appendix 3: Analysis of general insurance business non-liability claims (amount)")[0] == "general_non_liability"
    assert claims.classify("Appendix 8: Analysis of monthly summary of claims movement under long term insurance") is None


def test_claims_columns_by_heading():
    cols = claims.columns(["No", "Name of Insurer", "Claims outstanding at the beginning of the quarter",
                           "Claims intimated and revived during the quarter", "Claims revised during the quarter",
                           "Claims paid during the quarter", "Claims declined during the quarter",
                           "Claims closed as no claims during the quarter", "Claims outstanding at the end of the quarter"])
    assert cols == {"name": 1, "opening": 2, "intimated": 3, "revised": 4, "paid": 5, "declined": 6, "closed": 7, "closing": 8}


def test_registry_types():
    assert registry.std_type("Longterm") == "long_term"
    assert registry.std_type("Long term") == "long_term"
    assert registry.std_type("Composite (General )") == "composite"
    assert registry.std_type("Reinsurance (General)") == "reinsurer"
    assert registry.std_type("Microinsurance") == "microinsurer"
    assert registry.SEGMENT["composite"] == "life"


def test_scope_publishes_life_by_default():
    assert "life" in registry.scope("claims")
    assert "life" in registry.scope("registry")
