"""tests/unit/test_assessment_logic.py — deterministic assessment fallbacks."""

from app.assessment_parse import AssessmentResult
from app.phases.assessment import _derive_case, _is_weak_reasoning
from app.state.session import SessionState

_EMPTY = AssessmentResult()
_FULL = AssessmentResult(case_type="refugee", grounds=["political opinion"],
                         risk="high", countries=["Sweden"])


def test_weak_reasoning_is_deterministic():
    # Weak = no structured output, regardless of how the prose reads. A refusal or
    # a chatbot greeting both produce no @@ASSESSMENT block, so both are weak —
    # without pattern-matching the wording.
    refusal = "Based on the information provided, I cannot determine a case type at this time, sorry."
    greeting = ("Hello! I'm here to help you navigate your options. Could you tell me your "
                "preferred language? If you have documents, please share them when ready.")
    assert _is_weak_reasoning(refusal, _EMPTY)
    assert _is_weak_reasoning(greeting, _EMPTY)
    assert _is_weak_reasoning("too short", _EMPTY)        # length floor
    # A substantive analysis WITH structured output is not weak…
    good = (
        "Based on what you shared, you face a well-founded fear of persecution on "
        "political grounds. Under the 1951 Convention this is a refugee claim, and "
        "because you remain in your country you must seek protection abroad."
    )
    assert not _is_weak_reasoning(good, _FULL)
    # …and the SAME good prose with no structured output is treated as weak
    # (the model skipped the required block).
    assert _is_weak_reasoning(good, _EMPTY)


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
