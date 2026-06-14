"""tests/unit/test_assessment_logic.py — deterministic assessment fallbacks."""

from app.phases.assessment import _derive_case, _is_weak_reasoning
from app.state.session import SessionState


def test_weak_reasoning_detected():
    # refusals / non-answers
    assert _is_weak_reasoning("Based on the information provided, I cannot determine a case type.")
    assert _is_weak_reasoning("Additional details about your situation are needed to proceed.")
    assert _is_weak_reasoning("too short")
    # a substantive analysis is NOT weak
    good = (
        "Based on what you shared, you face a well-founded fear of persecution on "
        "political grounds. Under the 1951 Convention this is a refugee claim, and "
        "because you remain in your country you must seek protection abroad. "
        "Sweden, France and Italy all run active asylum procedures."
    )
    assert not _is_weak_reasoning(good)


def _seed(types, danger):
    s = SessionState()
    s.interview.persecution_types = types
    s.interview.immediate_danger = danger
    return s


def test_derive_case_from_interview():
    # clear protection grounds -> refugee
    case, grounds, risk = _derive_case(_seed(["Political", "Ethnic"], True))
    assert case == "refugee"
    assert "political opinion" in grounds
    assert risk == "high"
    # nothing claimed, no danger -> economic/other
    case2, grounds2, _ = _derive_case(_seed(["Other"], False))
    assert case2 == "economic_or_other"
    assert grounds2 == []
