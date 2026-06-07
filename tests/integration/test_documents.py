"""tests/integration/test_documents.py — document package generation (T053).

Seeds a complete session (real Ethiopia/Sudan scenario) and generates the four
PDFs with WeasyPrint. Asserts they are real, valid, non-empty, contain the
person's real data, and contain no placeholder tokens.
"""

from pathlib import Path

from agent.tools.country_lookup import lookup_country
from agent.tools.doc_generator import generate, zip_package
from app.state.session import SessionState, State


def _complete_session(origin="Ethiopia") -> SessionState:
    s = SessionState()
    for target in (State.INTAKE, State.SITUATION, State.HISTORY, State.GOALS,
                   State.REVIEW, State.ASSESSMENT, State.RECOMMENDATIONS, State.DOCUMENTS):
        s.transition_to(target)
    s.language = "Amharic"
    s.interview.origin_country = origin
    s.interview.current_country = "Sudan"
    s.interview.persecution_types = ["Political", "Ethnic"]
    s.interview.immediate_danger = True
    s.interview.family_situation = "two children"
    s.interview.documents_available = ["passport"]
    s.interview.languages_spoken = ["Amharic", "Arabic"]
    s.interview.free_text_history = "Armed men came to our village in November."
    s.assessment.convention_grounds = ["Political opinion"]
    s.assessment.recommended_countries = [lookup_country("Kenya")]
    s.selected_country = "Kenya"
    return s


def _pdf_text(path: Path) -> str:
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def test_generates_four_nonempty_valid_pdfs(tmp_path):
    docs = generate(_complete_session(), out_dir=tmp_path)
    assert len(docs) == 4
    for d in docs:
        assert d.path.exists()
        data = d.path.read_bytes()
        assert len(data) > 1000          # non-trivial
        assert data[:5] == b"%PDF-"      # valid PDF header


def test_personal_statement_contains_real_origin(tmp_path):
    docs = generate(_complete_session(), out_dir=tmp_path)
    statement = next(d for d in docs if d.key == "personal_statement")
    assert "Ethiopia" in _pdf_text(statement.path)  # SC-039: real data


def test_no_placeholder_tokens(tmp_path):
    docs = generate(_complete_session(), out_dir=tmp_path)
    for d in docs:
        text = _pdf_text(d.path)
        for forbidden in ("PLACEHOLDER", "[NAME]", "[COUNTRY]"):
            assert forbidden not in text, f"{forbidden} found in {d.key}"


def test_download_all_zip(tmp_path):
    docs = generate(_complete_session(), out_dir=tmp_path)
    zip_path = zip_package(docs, out_dir=tmp_path)
    assert zip_path.exists()
    assert zip_path.stat().st_size > 1000
