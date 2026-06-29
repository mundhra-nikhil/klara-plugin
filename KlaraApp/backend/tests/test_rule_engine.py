"""Unit tests for the reimagined document-processing engine:

  * ``docx_revisions.accept_all_revisions`` — accept-pending-changes on upload
  * ``rule_engine.analyze``               — deterministic automatic/visual rules
  * ``poc_rules.resolve_change_class``    — the automatic/visual decision

These are pure (no DB / no network), so they exercise the engine directly.
"""

import os
import tempfile

from lxml import etree

from src.services.ai_jobs import rule_engine
from src.services.ai_jobs.poc_rules import (
    AUTOMATIC_RULES, VISUAL_RULES, resolve_change_class,
)
from src.utils import docx_revisions

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def _w(tag):
    return f"{{{W}}}{tag}"


# ── helpers ─────────────────────────────────────────────────────────────────

def _fake_structured(texts, **para_overrides):
    """Build a minimal structured doc from paragraph text strings."""
    paras = []
    for i, t in enumerate(texts):
        p = {
            "index": i, "text": t, "is_heading": False, "alignment": "both",
            "line_spacing": {}, "font_sizes_pt": [], "fonts": [], "footnote_refs": [],
            "section_symbol_spacing_violations": [], "double_period_violations": [],
            "contains_straight_quote": '"' in t,
            "contains_curly_quote_open": "“" in t, "contains_curly_quote_close": "”" in t,
        }
        p.update(para_overrides)
        paras.append(p)
    return {"doc_default_font_size_pt": 12, "paragraphs": paras, "footnotes": []}


def _make_docx_with_revisions(path):
    """Create a tiny .docx whose paragraph carries one tracked insertion and one
    tracked deletion, plus a tracked format change."""
    from docx import Document
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn

    doc = Document()
    p = doc.add_paragraph()
    p.add_run("Keep ")

    ins = OxmlElement("w:ins")
    ins.set(qn("w:author"), "Reviewer"); ins.set(qn("w:id"), "1")
    r = OxmlElement("w:r"); t = OxmlElement("w:t"); t.text = "INSERTED"
    r.append(t); ins.append(r); p._p.append(ins)

    dl = OxmlElement("w:del")
    dl.set(qn("w:author"), "Reviewer"); dl.set(qn("w:id"), "2")
    r2 = OxmlElement("w:r"); dt = OxmlElement("w:delText"); dt.text = " DROP"
    r2.append(dt); dl.append(r2); p._p.append(dl)

    doc.save(path)


# ── accept_all_revisions ───────────────────────────────────────────────────

def test_has_revision_bytes_ignores_table_borders():
    # <w:insideH>/<w:insideV> are table-cell borders, NOT insertions.
    assert docx_revisions._has_revision_bytes(b"<w:insideH w:val=...") is False
    assert docx_revisions._has_revision_bytes(b"<w:ins w:id=...") is True
    assert docx_revisions._has_revision_bytes(b"<w:del>") is True


def test_accept_tree_unwraps_ins_drops_del_strips_change():
    xml = (
        f'<w:p xmlns:w="{W}">'
        f'<w:r><w:t>Keep </w:t></w:r>'
        f'<w:ins w:id="1"><w:r><w:t>IN</w:t></w:r></w:ins>'
        f'<w:del w:id="2"><w:r><w:delText>OUT</w:delText></w:r></w:del>'
        f'<w:rPrChange w:id="3"><w:rPr/></w:rPrChange>'
        f'</w:p>'
    )
    root = etree.fromstring(xml.encode())
    unwrapped, dropped, changes = docx_revisions._accept_tree(root)
    assert (unwrapped, dropped, changes) == (1, 1, 1)
    # No residual revision elements remain.
    assert root.find(f".//{_w('ins')}") is None
    assert root.find(f".//{_w('del')}") is None
    assert root.find(f".//{_w('rPrChange')}") is None
    # Inserted text survives; deleted text is gone.
    text = "".join(t.text or "" for t in root.iter(_w("t")))
    assert text == "Keep IN"
    assert "OUT" not in text


def test_accept_all_revisions_roundtrip():
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "rev.docx")
        _make_docx_with_revisions(path)
        assert docx_revisions.document_has_revisions(path) is True

        summary = docx_revisions.accept_all_revisions(path)
        assert summary["changed"] is True
        assert summary["unwrapped"] >= 1 and summary["dropped"] >= 1
        assert docx_revisions.document_has_revisions(path) is False

        from docx import Document
        text = Document(path).paragraphs[0].text
        assert "INSERTED" in text and "DROP" not in text

        # Idempotent: a second pass is a no-op.
        assert docx_revisions.accept_all_revisions(path)["changed"] is False


def test_accept_all_revisions_noop_on_clean_file():
    with tempfile.TemporaryDirectory() as d:
        from docx import Document
        path = os.path.join(d, "clean.docx")
        doc = Document(); doc.add_paragraph("Nothing tracked here."); doc.save(path)
        assert docx_revisions.accept_all_revisions(path)["changed"] is False


# ── rule_engine: AUTOMATIC class ────────────────────────────────────────────

def test_period_spacing_is_automatic_with_replacement():
    s = _fake_structured(["The motion was granted.The court agreed."])
    f = [x for x in rule_engine.analyze(s, []) if x["rule_id"] == 5]
    assert len(f) == 1
    assert f[0]["change_class"] == "automatic"
    assert f[0]["original_text"] == "granted.The"
    assert f[0]["replacement_text"] == "granted.  The"
    assert f[0]["location"]["change_class"] == "automatic"


def test_period_spacing_skips_abbreviations():
    s = _fake_structured(["Mr.Smith and Dr.Jones appeared."])
    assert [x for x in rule_engine.analyze(s, []) if x["rule_id"] == 5] == []


def test_section_symbol_is_automatic():
    s = _fake_structured(["Pursuant to §1234 and ¶5 of the code."])
    f = [x for x in rule_engine.analyze(s, []) if x["rule_id"] == 8]
    originals = {x["original_text"]: x["replacement_text"] for x in f}
    assert originals.get("§1234") == "§ 1234"
    assert originals.get("¶5") == "¶ 5"
    assert all(x["change_class"] == "automatic" for x in f)


def test_grammar_mechanics_fixes():
    s = _fake_structured([
        "The the plaintiff rested .",     # doubled word + space-before-period
        "See Smith,Jones for details.",   # missing space after comma
    ])
    f = [x for x in rule_engine.analyze(s, []) if x["rule_id"] == 15]
    fixes = {x["original_text"]: x["replacement_text"] for x in f}
    assert fixes.get("The the") == "The"
    assert fixes.get("rested .") == "rested."
    assert fixes.get("Smith,Jones") == "Smith, Jones"
    assert all(x["change_class"] == "automatic" for x in f)


def test_grammar_does_not_touch_numbers():
    s = _fake_structured(["The fee was 1,000 dollars at 12:30 today."])
    assert [x for x in rule_engine.analyze(s, []) if x["rule_id"] == 15] == []


def test_quotes_normalise_to_majority():
    # Majority curly → the lone straight pair is flagged + fixed to curly.
    s = _fake_structured([
        "The “Agreement” and the “Contract” were signed today.",
        'But the "Seller" did not deliver any of the goods.',
    ])
    f = [x for x in rule_engine.analyze(s, []) if x["rule_id"] == 4]
    assert len(f) == 1
    assert f[0]["original_text"] == '"Seller"'
    assert f[0]["replacement_text"] == "“Seller”"
    assert f[0]["change_class"] == "automatic"


def test_quotes_consistent_no_finding():
    s = _fake_structured(['The "A" and "B".', 'The "C" and "D".'])
    assert [x for x in rule_engine.analyze(s, []) if x["rule_id"] == 4] == []


# ── rule_engine: VISUAL class + page numbers ────────────────────────────────

def test_font_violation_is_visual_with_page():
    # Body majority is 12pt; one outlier paragraph at 14pt is the violation.
    s = _fake_structured([
        "Body text paragraph one that is long enough to count as prose here.",
        "Body text paragraph two that is long enough to count as prose here.",
        "Outlier paragraph three that is long enough to count as prose here.",
    ])
    s["paragraphs"][0]["font_sizes_pt"] = [12]
    s["paragraphs"][1]["font_sizes_pt"] = [12]
    s["paragraphs"][2]["font_sizes_pt"] = [14]   # odd one out
    page_map = [1, 2, 3]
    f = [x for x in rule_engine.analyze(s, page_map) if x["rule_id"] == 1]
    assert len(f) == 1
    assert f[0]["change_class"] == "visual"
    assert f[0]["location"]["paragraph"] == 2
    assert f[0]["location"]["page"] == 3
    assert not f[0]["original_text"]  # visual flags carry no text substitution


def test_clean_document_has_no_findings():
    s = _fake_structured([
        "This is a perfectly clean sentence with no issues at all here.",
        "Another fully compliant paragraph of body text in the document.",
    ])
    assert rule_engine.analyze(s, []) == []


# ── poc_rules.resolve_change_class ──────────────────────────────────────────

def test_resolve_change_class_logic():
    # Rule sets are mutually exclusive and cover all 18.
    assert AUTOMATIC_RULES == {4, 5, 8, 15}
    assert AUTOMATIC_RULES & VISUAL_RULES == set()
    assert AUTOMATIC_RULES | VISUAL_RULES == set(range(1, 19))
    # An automatic rule WITH a real replacement → automatic.
    assert resolve_change_class(5, "a.B", "a.  B") == "automatic"
    # An automatic rule with NO replacement → visual (still actionable by eye).
    assert resolve_change_class(5, None, None) == "visual"
    # A visual rule is always visual, even if text is supplied.
    assert resolve_change_class(1, "x", "y") == "visual"
