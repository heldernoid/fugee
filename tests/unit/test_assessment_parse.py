"""tests/unit/test_assessment_parse.py — @@ASSESSMENT block parsing."""

from app.assessment_parse import parse_assessment


def test_parses_full_block():
    text = (
        "Your situation fits the Convention on political opinion grounds.\n"
        "A nearby country with an active RSD process would suit you.\n"
        "@@ASSESSMENT\n"
        "grounds: Political opinion | Membership of a particular social group\n"
        "risk: high\n"
        "countries: Kenya | Uganda\n"
        "@@END"
    )
    visible, result = parse_assessment(text)
    assert "@@ASSESSMENT" not in visible
    assert visible.startswith("Your situation fits")
    assert result.grounds == ["Political opinion", "Membership of a particular social group"]
    assert result.risk == "high"
    assert result.countries == ["Kenya", "Uganda"]


def test_missing_block_returns_text_and_empty_result():
    visible, result = parse_assessment("Just reasoning, no block.")
    assert visible == "Just reasoning, no block."
    assert result.countries == []
    assert result.risk is None


def test_invalid_risk_becomes_none():
    _, result = parse_assessment("x\n@@ASSESSMENT\nrisk: catastrophic\ncountries: Kenya\n@@END")
    assert result.risk is None
    assert result.countries == ["Kenya"]


def test_block_without_end_marker():
    _, result = parse_assessment("x\n@@ASSESSMENT\nrisk: low\ncountries: Uganda")
    assert result.risk == "low"
    assert result.countries == ["Uganda"]
