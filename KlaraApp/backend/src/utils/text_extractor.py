"""DOCX text + structured-paragraph extraction utilities.

`docx_to_text` returns plain text (used for legacy callers).
`docx_to_html` returns a lightweight HTML preview for the side-by-side viewer.
`docx_to_structured_paragraphs` returns paragraph-level objects enriched with
formatting metadata the AI engine needs to evaluate the 18 POC checklist rules
(font size, line spacing, alignment, keepNext, footnote/heading classification,
quote characters, etc.). Without this metadata the LLM is reduced to guessing
about formatting from plain text.
"""

import html
import json
import re
import zipfile
import xml.etree.ElementTree as ET
import os
from typing import Any
from src.core.logger import get_logger_with_context

logger = get_logger_with_context()

W_NS = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'

COMMON_NAMESPACES = {
    'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main',
    'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships',
    'wp': 'http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing',
    've': 'http://schemas.openxmlformats.org/markup-compatibility/2006',
    'o': 'urn:schemas-microsoft-com:office:office',
    'v': 'urn:schemas-microsoft-com:vml',
    'm': 'http://schemas.openxmlformats.org/officeDocument/2006/math',
    'pic': 'http://schemas.openxmlformats.org/drawingml/2006/picture',
    'a': 'http://schemas.openxmlformats.org/drawingml/2006/main',
    'c': 'http://schemas.openxmlformats.org/drawingml/2006/chart',
    'lc': 'http://schemas.openxmlformats.org/drawingml/2006/lockedCanvas',
    'dgm': 'http://schemas.openxmlformats.org/drawingml/2006/diagram',
    'w10': 'urn:schemas-microsoft-com:office:word',
    'sl': 'http://schemas.openxmlformats.org/schemaLibrary/2006/main',
    'w14': 'http://schemas.microsoft.com/office/word/2010/wordml',
    'w15': 'http://schemas.microsoft.com/office/word/2012/wordml',
}

for prefix, uri in COMMON_NAMESPACES.items():
    ET.register_namespace(prefix, uri)


def accept_revisions_in_element(element):
    new_children = []
    for child in element:
        tag = child.tag.split('}', 1)[-1]
        if tag in ('ins', 'moveTo'):
            accept_revisions_in_element(child)
            new_children.extend(list(child))
        elif tag in ('del', 'moveFrom'):
            continue
        elif tag in ('pPrChange', 'rPrChange', 'tblPrChange', 'trPrChange', 'tcPrChange'):
            continue
        else:
            accept_revisions_in_element(child)
            new_children.append(child)
    element[:] = new_children


def accept_all_tracked_changes(docx_path: str):
    if not os.path.exists(docx_path):
        return

    import shutil
    import tempfile

    temp_dir = tempfile.mkdtemp()
    temp_zip_path = os.path.join(temp_dir, "temp.docx")

    try:
        with zipfile.ZipFile(docx_path, 'r') as yin:
            with zipfile.ZipFile(temp_zip_path, 'w', zipfile.ZIP_DEFLATED) as yout:
                for item in yin.infolist():
                    data = yin.read(item.filename)
                    if item.filename.startswith("word/") and item.filename.endswith(".xml"):
                        try:
                            root = ET.fromstring(data)
                            accept_revisions_in_element(root)
                            new_data = ET.tostring(root, encoding='utf-8')
                            yout.writestr(item, new_data)
                        except Exception as e:
                            logger.error(f"Failed to process XML in {item.filename}: {e}")
                            yout.writestr(item, data)
                    else:
                        yout.writestr(item, data)
        shutil.move(temp_zip_path, docx_path)
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def docx_to_text(path: str) -> str:
    """Extract plain text from a .docx file."""
    try:
        if not os.path.exists(path):
            return ""
        with zipfile.ZipFile(path) as z:
            xml_content = z.read('word/document.xml')
            root = ET.fromstring(xml_content)

            text_runs = []
            for elem in root.iter():
                if elem.tag.endswith('}t'):
                    text_runs.append(elem.text or '')
                elif elem.tag.endswith('}p') or elem.tag.endswith('}br') or elem.tag.endswith('}cr'):
                    text_runs.append('\n')

            return "".join(text_runs)
    except Exception as e:
        logger.error(f"Error extracting text from docx file {path}: {e}")
        return ""


def _para_text_and_style(p_elem) -> tuple[str, str, bool]:
    """Return (text, style_name, is_heading) for a <w:p> paragraph element."""
    style_name = ""
    is_heading = False
    p_pr = p_elem.find(f'{{{W_NS}}}pPr')
    if p_pr is not None:
        p_style = p_pr.find(f'{{{W_NS}}}pStyle')
        if p_style is not None:
            style_name = p_style.get(f'{{{W_NS}}}val', '') or ''
            if style_name.lower().startswith('heading') or style_name.lower() == 'title':
                is_heading = True

    parts = []
    for t in p_elem.iter(f'{{{W_NS}}}t'):
        parts.append(t.text or '')
    for _ in p_elem.iter(f'{{{W_NS}}}br'):
        parts.append('\n')
    text = ''.join(parts).strip()
    return text, style_name, is_heading


def docx_to_html(path: str) -> str:
    """Lightweight DOCX → HTML preview. Preserves paragraph structure
    and headings well enough for an in-app document viewer. Wraps each
    paragraph in <p data-para-index="N"> so the frontend can highlight
    the exact paragraph referenced by an AI finding."""
    if not os.path.exists(path):
        return ""
    try:
        with zipfile.ZipFile(path) as z:
            xml_content = z.read('word/document.xml')
            root = ET.fromstring(xml_content)

        out: list[str] = []
        body = root.find(f'{{{W_NS}}}body')
        if body is None:
            return ""

        para_index = 0
        for child in body:
            tag = child.tag.split('}', 1)[-1]
            if tag == 'p':
                text, style, is_heading = _para_text_and_style(child)
                if not text:
                    out.append(f'<p data-para-index="{para_index}">&nbsp;</p>')
                    para_index += 1
                    continue
                escaped = html.escape(text)
                if is_heading:
                    level = '2'
                    if style.lower().startswith('heading'):
                        digits = ''.join(c for c in style if c.isdigit())
                        if digits:
                            level = digits[0]
                            if int(level) < 1:
                                level = '1'
                            if int(level) > 4:
                                level = '4'
                    out.append(f'<h{level} data-para-index="{para_index}">{escaped}</h{level}>')
                else:
                    out.append(f'<p data-para-index="{para_index}">{escaped}</p>')
                para_index += 1
            elif tag == 'tbl':
                out.append('<table style="border-collapse:collapse;margin:8px 0">')
                for row in child.iter(f'{{{W_NS}}}tr'):
                    out.append('<tr>')
                    for cell in row.iter(f'{{{W_NS}}}tc'):
                        cell_text_parts = []
                        for p_elem in cell.iter(f'{{{W_NS}}}p'):
                            t, _, _ = _para_text_and_style(p_elem)
                            if t:
                                cell_text_parts.append(t)
                        cell_text = html.escape('\n'.join(cell_text_parts))
                        out.append(
                            f'<td style="border:1px solid #ddd;padding:4px 8px;vertical-align:top">{cell_text}</td>'
                        )
                    out.append('</tr>')
                out.append('</table>')
        return ''.join(out)
    except Exception as e:
        logger.error(f"Error converting docx to html {path}: {e}")
        return ""


# Author name the engine stamps on AI-suggested tracked changes (see
# document_comparison_service._apply_tracked_changes_to_paragraph). Revisions by
# this author that are still *pending* (not yet accepted by a human) are treated
# as "not part of the document" when we resolve the final text — the comparison
# must reflect only manual edits and changes the reviewer actually accepted.
AI_REVISION_AUTHOR = "Klara AI"


def _is_ai_author(author: str | None) -> bool:
    """True when a tracked-change author is the AI engine (not a human reviewer)."""
    return bool(author) and "klara" in author.strip().lower()


def _collect_deltext(elem) -> str:
    """Concatenate the <w:delText> (deleted-text) nodes under a <w:del> element."""
    return "".join(t.text or "" for t in elem.iter(f'{{{W_NS}}}delText'))


def _resolve_node_text(elem) -> str:
    """Recursively gather a paragraph's *final, resolved* text, honoring tracked
    changes the way "accept all human edits, reject pending AI edits" would:

      • <w:ins> by a human reviewer  → keep (the insertion is accepted)
      • <w:ins> by the AI engine     → drop (a pending AI suggestion — excluded)
      • <w:del> by a human reviewer  → drop the deleted text (deletion accepted)
      • <w:del> by the AI engine     → restore the deleted text (suggestion rejected)
      • plain <w:t>                  → keep (already baked into the document)

    The net result is "original document + manual edits + accepted AI changes",
    which is exactly what the before/after comparison should diff against the
    pristine original."""
    parts: list[str] = []
    for child in elem:
        tag = child.tag.split('}', 1)[-1]
        if tag == 'ins':
            author = child.get(f'{{{W_NS}}}author', '')
            if _is_ai_author(author):
                continue  # pending AI insertion → not in the accepted document
            parts.append(_resolve_node_text(child))
        elif tag == 'del':
            author = child.get(f'{{{W_NS}}}author', '')
            if _is_ai_author(author):
                parts.append(_collect_deltext(child))  # AI deletion rejected → restore
            # else: human deletion accepted → contribute nothing
        elif tag == 't':
            parts.append(child.text or '')
        elif tag == 'tab':
            parts.append('\t')
        elif tag in ('br', 'cr'):
            parts.append('\n')
        elif tag == 'delText':
            continue  # bare deleted text outside a <w:del> — treat as removed
        else:
            # w:r, w:hyperlink, w:smartTag, … — descend to find text nodes.
            parts.append(_resolve_node_text(child))
    return "".join(parts)


def docx_to_resolved_paragraphs(path: str) -> list[str]:
    """Return the document's paragraphs as final, tracked-change-resolved text.

    Used by the change-comparison viewer. For a pristine document (no revisions)
    this is just the plain paragraph text; for an edited document it reflects the
    manual edits and the AI changes the reviewer accepted, with still-pending AI
    suggestions excluded (see ``_resolve_node_text``). Includes paragraphs nested
    in tables, in document order."""
    if not os.path.exists(path):
        return []
    try:
        with zipfile.ZipFile(path) as z:
            root = ET.fromstring(z.read('word/document.xml'))
    except Exception as e:
        logger.error(f"Error reading paragraphs from docx {path}: {e}")
        return []

    body = root.find(f'{{{W_NS}}}body')
    if body is None:
        return []
    return [_resolve_node_text(p) for p in body.iter(f'{{{W_NS}}}p')]


def estimate_page_map(
    path: str, chars_per_line: int = 90, lines_per_page: int = 28
) -> list[int]:
    """Estimate a 1-based page number for each paragraph (same order as
    ``docx_to_resolved_paragraphs``).

    The .docx only encodes *explicit* page breaks; most pagination in a legal
    pleading is soft (driven by the renderer), so we approximate it the way the
    document is laid out: ~``lines_per_page`` numbered lines per page, each
    paragraph consuming ``ceil(len/chars_per_line)`` lines (blank paragraphs —
    used for double-spacing — count as one line). Explicit page breaks snap to
    the next page boundary. Calibrated to match the editor's page count closely;
    used only to label and group changes for navigation, not for precise
    layout."""
    if not os.path.exists(path):
        return []
    try:
        with zipfile.ZipFile(path) as z:
            root = ET.fromstring(z.read('word/document.xml'))
    except Exception as e:
        logger.error(f"Error estimating page map for docx {path}: {e}")
        return []

    body = root.find(f'{{{W_NS}}}body')
    if body is None:
        return []

    pages: list[int] = []
    cum = 0
    for p in body.iter(f'{{{W_NS}}}p'):
        txt = _resolve_node_text(p)
        pages.append(1 + cum // lines_per_page)
        if txt.strip():
            cum += max(1, -(-len(txt) // chars_per_line))  # ceil division
        else:
            cum += 1
        # An explicit page break pushes following content to the next page.
        if any(
            br.get(f'{{{W_NS}}}type') == 'page' for br in p.iter(f'{{{W_NS}}}br')
        ):
            cum = ((cum // lines_per_page) + 1) * lines_per_page
    return pages


def _read_footnotes(z: zipfile.ZipFile) -> dict[str, dict[str, Any]]:
    """Extract footnote bodies and their primary run formatting."""
    out: dict[str, dict[str, Any]] = {}
    try:
        xml_content = z.read('word/footnotes.xml')
    except KeyError:
        return out
    try:
        root = ET.fromstring(xml_content)
    except ET.ParseError:
        return out

    for fn in root.iter(f'{{{W_NS}}}footnote'):
        fn_id = fn.get(f'{{{W_NS}}}id', '')
        fn_type = fn.get(f'{{{W_NS}}}type', '') or ''
        if fn_type in ('separator', 'continuationSeparator'):
            continue
        text_parts: list[str] = []
        sizes: list[int] = []
        fonts: list[str] = []
        for p_elem in fn.iter(f'{{{W_NS}}}p'):
            for r_elem in p_elem.iter(f'{{{W_NS}}}r'):
                r_pr = r_elem.find(f'{{{W_NS}}}rPr')
                if r_pr is not None:
                    sz = r_pr.find(f'{{{W_NS}}}sz')
                    if sz is not None:
                        val = sz.get(f'{{{W_NS}}}val')
                        if val and val.isdigit():
                            # Word stores font size in half-points
                            sizes.append(int(val) // 2)
                    rfont = r_pr.find(f'{{{W_NS}}}rFonts')
                    if rfont is not None:
                        for attr in ('ascii', 'hAnsi', 'cs'):
                            v = rfont.get(f'{{{W_NS}}}{attr}')
                            if v:
                                fonts.append(v)
                for t in r_elem.iter(f'{{{W_NS}}}t'):
                    text_parts.append(t.text or '')
        out[fn_id] = {
            'text': ''.join(text_parts).strip(),
            'font_sizes_pt': sorted(set(sizes)),
            'fonts': sorted({f for f in fonts}),
        }
    return out


def _read_styles_default_font_size(z: zipfile.ZipFile) -> int | None:
    """Return the document default font size in points, if specified."""
    try:
        xml_content = z.read('word/styles.xml')
    except KeyError:
        return None
    try:
        root = ET.fromstring(xml_content)
    except ET.ParseError:
        return None
    doc_defaults = root.find(f'{{{W_NS}}}docDefaults')
    if doc_defaults is None:
        return None
    rpr = doc_defaults.find(f'.//{{{W_NS}}}rPrDefault/{{{W_NS}}}rPr')
    if rpr is None:
        return None
    sz = rpr.find(f'{{{W_NS}}}sz')
    if sz is None:
        return None
    val = sz.get(f'{{{W_NS}}}val')
    if val and val.isdigit():
        return int(val) // 2
    return None


def _aggregate_para_runs(p_elem) -> tuple[list[int], list[str], list[str]]:
    """Return (sizes_pt, fonts, run_texts) for runs inside a paragraph."""
    sizes: list[int] = []
    fonts: list[str] = []
    run_texts: list[str] = []
    for r_elem in p_elem.iter(f'{{{W_NS}}}r'):
        r_pr = r_elem.find(f'{{{W_NS}}}rPr')
        if r_pr is not None:
            sz = r_pr.find(f'{{{W_NS}}}sz')
            if sz is not None:
                v = sz.get(f'{{{W_NS}}}val')
                if v and v.isdigit():
                    sizes.append(int(v) // 2)
            rfont = r_pr.find(f'{{{W_NS}}}rFonts')
            if rfont is not None:
                for attr in ('ascii', 'hAnsi', 'cs'):
                    val = rfont.get(f'{{{W_NS}}}{attr}')
                    if val:
                        fonts.append(val)
        parts: list[str] = []
        for t in r_elem.iter(f'{{{W_NS}}}t'):
            parts.append(t.text or '')
        run_texts.append(''.join(parts))
    return sizes, fonts, run_texts


def docx_to_structured_paragraphs(path: str) -> dict[str, Any]:
    """Return paragraph-level structured representation suitable for AI analysis.

    Output shape:
    {
      "doc_default_font_size_pt": 12,
      "paragraphs": [
        {
          "index": 0,
          "text": "...",
          "style": "Heading1",
          "is_heading": true,
          "alignment": "justify",
          "line_spacing": {"line": 480, "line_rule": "auto"},
          "space_before": 0,
          "space_after": 0,
          "keep_next": false,
          "font_sizes_pt": [14],
          "fonts": ["Times New Roman"],
          "contains_curly_quote_open": false,
          "contains_curly_quote_close": false,
          "contains_straight_quote": true,
          "section_symbol_spacing_violations": ["§17200"],
          "double_period_violations": ["granted.This"]
        }
      ],
      "footnotes": [...]
    }
    """
    out: dict[str, Any] = {
        "doc_default_font_size_pt": None,
        "paragraphs": [],
        "footnotes": [],
        "footnote_to_para_index": {},
    }
    if not os.path.exists(path):
        return out
    try:
        with zipfile.ZipFile(path) as z:
            xml_content = z.read('word/document.xml')
            root = ET.fromstring(xml_content)
            out["doc_default_font_size_pt"] = _read_styles_default_font_size(z)
            fn_map = _read_footnotes(z)

        body = root.find(f'{{{W_NS}}}body')
        if body is None:
            return out

        para_index = 0
        for p_elem in body.iter(f'{{{W_NS}}}p'):
            text, style, is_heading = _para_text_and_style(p_elem)
            sizes, fonts, _runs = _aggregate_para_runs(p_elem)

            # Map footnoteReference to paragraph index
            for fn_ref in p_elem.iter(f'{{{W_NS}}}footnoteReference'):
                fn_id = fn_ref.get(f'{{{W_NS}}}id')
                if fn_id:
                    out["footnote_to_para_index"][fn_id] = para_index

            alignment = None
            line_spacing: dict[str, Any] = {}
            space_before = None
            space_after = None
            keep_next = False
            p_pr = p_elem.find(f'{{{W_NS}}}pPr')
            if p_pr is not None:
                jc = p_pr.find(f'{{{W_NS}}}jc')
                if jc is not None:
                    alignment = jc.get(f'{{{W_NS}}}val')
                spacing = p_pr.find(f'{{{W_NS}}}spacing')
                if spacing is not None:
                    for attr in ('line', 'lineRule', 'before', 'after'):
                        v = spacing.get(f'{{{W_NS}}}{attr}')
                        if v is None:
                            continue
                        if attr == 'line':
                            line_spacing["line"] = int(v) if v.lstrip('-').isdigit() else v
                        elif attr == 'lineRule':
                            line_spacing["line_rule"] = v
                        elif attr == 'before':
                            space_before = int(v) if v.lstrip('-').isdigit() else v
                        elif attr == 'after':
                            space_after = int(v) if v.lstrip('-').isdigit() else v
                kn = p_pr.find(f'{{{W_NS}}}keepNext')
                if kn is not None:
                    val = kn.get(f'{{{W_NS}}}val')
                    keep_next = val is None or val.lower() in ('1', 'true', 'on')

            # Footnote reference ids in this paragraph (so a footnote-level
            # finding can be labelled with the page where it's referenced).
            footnote_refs: list[str] = []
            for ref in p_elem.iter(f'{{{W_NS}}}footnoteReference'):
                rid = ref.get(f'{{{W_NS}}}id')
                if rid:
                    footnote_refs.append(rid)

            # Detect quote-char usage at the paragraph level
            curly_open = '“' in text
            curly_close = '”' in text
            curly_apo_open = '‘' in text
            curly_apo_close = '’' in text
            straight = '"' in text or "'" in text

            # § followed immediately by digit (no space)
            section_violations = re.findall(r'§(?=\d)\d+', text)
            # period followed immediately by uppercase letter (no space after).
            # Match when preceded by a lowercase letter OR a digit (e.g. "2026.Nexogen")
            # so we catch date-ended sentence-merge errors too.
            # Allow common abbreviations (Mr., Mrs., Dr., U.S., etc.)
            double_period_violations = []
            for m in re.finditer(r'(?:[a-z]|[0-9])\.([A-Z][a-z])', text):
                snippet = text[max(0, m.start()-4): m.end()+4]
                if any(abbr in snippet for abbr in ('Mr.', 'Mrs.', 'Ms.', 'Dr.', 'U.S.', 'No.', 'Inc.', 'St.', 'Ave.')):
                    continue
                # Skip footnote markers like ".5Nexogen" (digit followed by lowercase)
                double_period_violations.append(text[m.start(): m.end()])

            out["paragraphs"].append({
                "index": para_index,
                "text": text,
                "style": style,
                "is_heading": is_heading,
                "alignment": alignment,
                "line_spacing": line_spacing,
                "space_before": space_before,
                "space_after": space_after,
                "keep_next": keep_next,
                "font_sizes_pt": sorted(set(sizes)),
                "fonts": sorted({f for f in fonts}),
                "contains_curly_quote_open": curly_open or curly_apo_open,
                "contains_curly_quote_close": curly_close or curly_apo_close,
                "contains_straight_quote": straight,
                "section_symbol_spacing_violations": section_violations,
                "double_period_violations": double_period_violations,
                "footnote_refs": footnote_refs,
            })
            para_index += 1

        out["footnotes"] = [
            {"id": fid, **info} for fid, info in fn_map.items()
        ]
    except Exception as e:
        logger.error(f"Error extracting structured paragraphs from {path}: {e}")
    return out


def compute_rule_violations(structured: dict[str, Any]) -> dict[str, Any]:
    """Pre-compute deterministic violation candidates so the LLM only has to
    confirm and describe (not search). Returns per-rule arrays of paragraph
    indexes / offending strings. The LLM is instructed to emit one finding per
    entry here (after validating the candidate)."""
    paras: list[dict[str, Any]] = structured.get("paragraphs", []) or []
    footnotes: list[dict[str, Any]] = structured.get("footnotes", []) or []
    default_body = structured.get("doc_default_font_size_pt")

    body_sizes: list[int] = []
    for p in paras:
        if not p.get("is_heading"):
            for s in p.get("font_sizes_pt", []) or []:
                body_sizes.append(s)
    body_size_mode = None
    if body_sizes:
        # mode (most common)
        from collections import Counter
        body_size_mode = Counter(body_sizes).most_common(1)[0][0]
    if not body_size_mode:
        body_size_mode = default_body or 12

    expected_footnote_size = 10 if body_size_mode == 12 else (14 if body_size_mode == 14 else None)
    footnote_to_para_index = structured.get("footnote_to_para_index", {})

    # Rule 1 — Font consistency: footnote sizes don't match expectation
    rule1: list[dict[str, Any]] = []
    for fn in footnotes:
        sizes = fn.get("font_sizes_pt") or []
        if not sizes:
            continue
        for s in sizes:
            if expected_footnote_size is not None and s != expected_footnote_size:
                fn_id = fn.get("id")
                rule1.append({
                    "footnote_id": fn_id,
                    "paragraph": footnote_to_para_index.get(fn_id),
                    "got_pt": s,
                    "expected_pt": expected_footnote_size,
                    "body_size_pt": body_size_mode,
                    "snippet": (fn.get("text", "") or "")[:160],
                })
                break

    # Body paragraphs with font size != mode (Rule 1 / Rule 18 inconsistency)
    rule1_body: list[dict[str, Any]] = []
    for p in paras:
        if p.get("is_heading"):
            continue
        sizes = p.get("font_sizes_pt") or []
        if not sizes:
            continue
        odd = [s for s in sizes if s != body_size_mode]
        if odd and len(p.get("text", "")) > 5:
            rule1_body.append({
                "paragraph": p["index"],
                "got_pt": odd,
                "expected_pt": body_size_mode,
                "snippet": (p.get("text", "") or "")[:160],
            })

    # Identify body paragraphs heuristically: substantive prose (>= 80 chars),
    # not centered (so skip captions/titles), not right-aligned (so skip signatures),
    # and not an ALL-CAPS title block.
    def _is_body(p: dict[str, Any]) -> bool:
        if p.get("is_heading"):
            return False
        text = (p.get("text") or "").strip()
        if len(text) < 80:
            return False
        align = p.get("alignment")
        if align in ("center", "right"):
            return False
        letters = [c for c in text if c.isalpha()]
        if letters and sum(1 for c in letters if c.isupper()) / len(letters) > 0.7:
            # All-caps "title block" line — not body prose.
            return False
        return True

    # Rule 2 — line spacing: expect 480 (24pt) for body paragraphs;
    # flag body paragraphs with line ≤ 280 regardless of line_rule.
    rule2: list[dict[str, Any]] = []
    for p in paras:
        if not _is_body(p):
            continue
        ls = p.get("line_spacing") or {}
        line = ls.get("line")
        rule = ls.get("line_rule")
        text = (p.get("text") or "").strip()
        if isinstance(line, int) and line and line <= 280:
            rule2.append({
                "paragraph": p["index"],
                "got_line": line,
                "expected_line": 480,
                "line_rule": rule,
                "snippet": text[:160],
            })

    # Rule 4 — quote mark mixing in same paragraph
    rule4: list[dict[str, Any]] = []
    for p in paras:
        if p.get("contains_straight_quote") and (
            p.get("contains_curly_quote_open") or p.get("contains_curly_quote_close")
        ):
            rule4.append({
                "paragraph": p["index"],
                "snippet": (p.get("text") or "")[:200],
            })

    # Rule 5 — period spacing
    rule5: list[dict[str, Any]] = []
    for p in paras:
        viol = p.get("double_period_violations") or []
        if viol:
            rule5.append({
                "paragraph": p["index"],
                "examples": viol[:5],
                "snippet": (p.get("text") or "")[:200],
            })

    # Rule 6 — justification: identify modal alignment, flag deviants in body paragraphs
    aligns: list[str] = [p.get("alignment") or "left" for p in paras if not p.get("is_heading") and (p.get("text") or "").strip()]
    align_mode = None
    if aligns:
        from collections import Counter
        align_mode = Counter(aligns).most_common(1)[0][0]
    rule6: list[dict[str, Any]] = []
    if align_mode in ("both", "justify"):
        for p in paras:
            if not _is_body(p):
                continue
            a = p.get("alignment") or "left"
            # Only flag LEFT-aligned body paragraphs as Rule 6 violations.
            # Center/right alignment is intentional for captions, titles, signatures.
            if a == "left":
                text = (p.get("text") or "").strip()
                rule6.append({
                    "paragraph": p["index"],
                    "got_alignment": a,
                    "expected_alignment": "both/justify",
                    "snippet": text[:160],
                })

    # Rule 7 — heading without keepNext (top-level section headings only).
    # We only flag top-level Roman-numeral headings (I., II., III., IV., V., VI., …)
    # because sub-headings (A., B., C.) routinely have keepNext=False and that's
    # not actually a violation in legal pleadings.
    # Exclude TOC entries: they match the heading regex but are filled with dots
    # ("II. Statement of Facts......16") — flagging them is a false positive AND
    # their text appears on page 1 (TOC), making navigation land on the wrong page.
    top_level_head_re = re.compile(r'^(?:IX|IV|V?I{0,3}|X)\.\s+\S', re.IGNORECASE)
    rule7: list[dict[str, Any]] = []
    for p in paras:
        text = (p.get("text") or "").strip()
        if not text or len(text) > 120:
            continue
        if not top_level_head_re.match(text):
            continue
        # Skip TOC entries: they contain 3+ consecutive dots before the page number.
        if '...' in text:
            continue
        if not p.get("keep_next"):
            rule7.append({
                "paragraph": p["index"],
                "snippet": text[:160],
            })

    # Rule 8 — section symbol spacing
    rule8: list[dict[str, Any]] = []
    for p in paras:
        viol = p.get("section_symbol_spacing_violations") or []
        if viol:
            rule8.append({
                "paragraph": p["index"],
                "examples": viol[:5],
                "snippet": (p.get("text") or "")[:200],
            })

    # Rule 15 — spelling & grammar (automatic)
    rule15: list[dict[str, Any]] = []
    uk_us_map = {
        r'\borganisation(s)?\b': 'organization\\1',
        r'\bbehaviour(s)?\b': 'behavior\\1',
        r'\bcolour(s)?\b': 'color\\1',
        r'\bdefence(s)?\b': 'defense\\1',
        r'\banalyse(s)?\b': 'analyze\\1',
        r'\bcancelled\b': 'canceled',
        r'\bjudgement(s)?\b': 'judgment\\1',
        r'\backnowledgement(s)?\b': 'acknowledgment\\1',
    }
    for p in paras:
        text = p.get("text") or ""
        # Check repeated words
        repeated_match = re.search(r'\b([a-zA-Z]+)\s+\1\b', text, re.IGNORECASE)
        if repeated_match:
            word = repeated_match.group(1)
            rule15.append({
                "paragraph": p["index"],
                "type": "repeated_word",
                "match": repeated_match.group(0),
                "original": repeated_match.group(0),
                "replacement": word,
                "snippet": text[max(0, repeated_match.start()-40): repeated_match.end()+40],
            })
            continue

        # Check UK/US spelling variants
        for pattern, replacement in uk_us_map.items():
            matches = list(re.finditer(pattern, text, re.IGNORECASE))
            if matches:
                for match in matches:
                    orig = match.group(0)
                    repl = orig
                    if orig.lower().startswith("organisation"):
                        repl = "organization" + ("s" if orig.endswith("s") else "")
                    elif orig.lower() == "behaviour":
                        repl = "behavior"
                    elif orig.lower() == "colour":
                        repl = "color"
                    elif orig.lower() == "defence":
                        repl = "defense"
                    elif orig.lower().startswith("analyse"):
                        repl = "analyze" + ("s" if orig.endswith("s") else "")
                    elif orig.lower() == "cancelled":
                        repl = "canceled"
                    elif orig.lower().startswith("judgement"):
                        repl = "judgment" + ("s" if orig.endswith("s") else "")
                    elif orig.lower().startswith("acknowledgement"):
                        repl = "acknowledgment" + ("s" if orig.endswith("s") else "")
                    
                    if orig.istitle():
                        repl = repl.title()
                    elif orig.isupper():
                        repl = repl.upper()

                    rule15.append({
                        "paragraph": p["index"],
                        "type": "spelling_typo",
                        "match": orig,
                        "original": orig,
                        "replacement": repl,
                        "snippet": text[max(0, match.start()-40): match.end()+40],
                    })

    return {
        "body_size_mode_pt": body_size_mode,
        "expected_footnote_size_pt": expected_footnote_size,
        "align_mode": align_mode,
        "violations": {
            "rule_1_footnote_font": rule1,
            "rule_1_body_font": rule1_body,
            "rule_2_line_spacing": rule2,
            "rule_4_mixed_quotes": rule4,
            "rule_5_period_spacing": rule5,
            "rule_6_justification": rule6,
            "rule_7_orphan_heading": rule7,
            "rule_8_section_symbol": rule8,
            "rule_15_spelling": rule15,
        },
    }


def structured_to_prompt_text(structured: dict[str, Any], max_paragraphs: int = 140) -> str:
    """Format the structured representation as a compact, readable block
    the LLM can use directly. Truncates very long documents.
    Skips empty paragraphs entirely (the byte-level layout doesn't matter to the AI)."""
    all_paras = structured.get("paragraphs", []) or []
    paras = [p for p in all_paras if (p.get("text") or "").strip()]
    truncated = paras[:max_paragraphs]
    lines: list[str] = []
    lines.append(
        f"Document default body font size (pt): {structured.get('doc_default_font_size_pt')}"
    )
    lines.append(
        f"Total paragraphs: {len(all_paras)} ({len(paras)} non-empty, showing {len(truncated)})"
    )

    # Pre-computed deterministic violations (the LLM only needs to confirm)
    violations = compute_rule_violations(structured)
    lines.append(f"Body font size mode (pt): {violations.get('body_size_mode_pt')}")
    lines.append(f"Expected footnote font size (pt): {violations.get('expected_footnote_size_pt')}")
    lines.append(f"Modal alignment: {violations.get('align_mode')}")
    lines.append("")
    lines.append("=== PRE-COMPUTED RULE VIOLATIONS (treat as authoritative) ===")
    lines.append(json.dumps(violations.get("violations", {}), indent=2)[:6000])
    lines.append("")
    lines.append("=== PARAGRAPHS (with formatting metadata) ===")
    for p in truncated:
        meta_bits = [
            f"idx={p['index']}",
            f"style={p['style'] or '-'}",
            f"heading={p['is_heading']}",
            f"align={p['alignment'] or '-'}",
            f"line={p['line_spacing'].get('line', '-')}",
            f"lineRule={p['line_spacing'].get('line_rule', '-')}",
            f"keepNext={p['keep_next']}",
            f"sizes_pt={p['font_sizes_pt'] or '-'}",
            f"fonts={p['fonts'] or '-'}",
            f"curlyQ={'Y' if p['contains_curly_quote_open'] or p['contains_curly_quote_close'] else 'N'}",
            f"straightQ={'Y' if p['contains_straight_quote'] else 'N'}",
        ]
        if p.get("section_symbol_spacing_violations"):
            meta_bits.append(f"sectionSymbolViolations={p['section_symbol_spacing_violations']}")
        if p.get("double_period_violations"):
            meta_bits.append(f"periodSpacingViolations={p['double_period_violations']}")
        lines.append("[" + " | ".join(meta_bits) + "]")
        lines.append(p["text"])
        lines.append("")
    if structured.get("footnotes"):
        lines.append("=== FOOTNOTES ===")
        for fn in structured["footnotes"]:
            lines.append(
                f"footnote id={fn.get('id')} sizes_pt={fn.get('font_sizes_pt')} fonts={fn.get('fonts')}"
            )
            lines.append(fn.get("text", ""))
            lines.append("")
    return "\n".join(lines)


def extract_text_from_file(path: str) -> str:
    """Extract text from a file based on its extension."""
    if not os.path.exists(path):
        return ""

    ext = os.path.splitext(path)[1].lower()
    if ext == '.docx':
        return docx_to_text(path)
    elif ext in ('.txt', '.md', '.json', '.xml'):
        try:
            with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                return f.read()
        except Exception as e:
            logger.error(f"Error reading text file {path}: {e}")
            return ""
    else:
        return ""


def extract_structured_from_file(path: str) -> dict[str, Any] | None:
    if not os.path.exists(path):
        return None
    if os.path.splitext(path)[1].lower() != '.docx':
        return None
    return docx_to_structured_paragraphs(path)
