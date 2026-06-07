"""tests/integration/test_documents.py — document package (PDF + editable Word).

Seeds a complete session and generates the package with the deterministic
fallback statement (no model needed). Asserts real, valid, non-empty PDF + DOCX
files containing the person's real data and no forbidden placeholder tokens.
"""

from pathlib import Path

from agent.tools.country_lookup import lookup_country
from agent.tools.doc_generator import all_files, generate, zip_package
from app.state.session import SessionState, State


def _complete_session(origin="Ethiopia") -> SessionState:
    s = SessionState()
    for target in (State.INTAKE, State.SITUATION, State.HISTORY, State.GOALS,
                   State.REVIEW, State.ASSESSMENT, State.RECOMMENDATIONS, State.DOCUMENTS):
        s.transition_to(target)
    s.language = "English"
    s.interview.origin_country = origin
    s.interview.current_country = "Sudan"
    s.interview.free_text_history = "Armed men came to our village in November."
    s.interview.immediate_danger = True
    s.interview.documents_available = ["Passport"]
    s.interview.languages_spoken = ["Amharic", "Arabic"]
    s.assessment.convention_grounds = ["Political opinion"]
    s.assessment.recommended_countries = [lookup_country("Kenya")]
    s.selected_country = "Kenya"
    return s


def _pdf_text(path: Path) -> str:
    from pypdf import PdfReader
    return "\n".join(page.extract_text() or "" for page in PdfReader(str(path)).pages)


def test_generates_four_docs_each_pdf_and_docx(tmp_path):
    docs = generate(_complete_session(), out_dir=tmp_path)
    assert len(docs) == 4
    for d in docs:
        assert d.pdf_path.exists() and d.docx_path.exists()
        pdf = d.pdf_path.read_bytes()
        assert pdf[:5] == b"%PDF-" and len(pdf) > 1000
        docx = d.docx_path.read_bytes()
        assert docx[:2] == b"PK" and len(docx) > 1000  # .docx is a zip


def test_personal_statement_contains_real_origin(tmp_path):
    docs = generate(_complete_session(), out_dir=tmp_path)
    ps = next(d for d in docs if d.key == "personal_statement")
    assert "Ethiopia" in _pdf_text(ps.pdf_path)


def test_no_forbidden_placeholder_tokens(tmp_path):
    docs = generate(_complete_session(), out_dir=tmp_path)
    for d in docs:
        text = _pdf_text(d.pdf_path)
        for forbidden in ("PLACEHOLDER", "[NAME]", "[COUNTRY]"):
            assert forbidden not in text, f"{forbidden} in {d.key}"


def test_download_all_zip_has_eight_files(tmp_path):
    docs = generate(_complete_session(), out_dir=tmp_path)
    assert len(all_files(docs)) == 8  # 4 docs × (pdf + docx)
    zip_path = zip_package(docs, out_dir=tmp_path)
    assert zip_path.exists() and zip_path.stat().st_size > 2000
