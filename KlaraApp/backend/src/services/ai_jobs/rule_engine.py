"""Deterministic, pure-Python QA rule engine for the 18-rule POC checklist.

This is the single authoritative source for the rules the engine can evaluate
*without* a language model. It produces two kinds of findings:

  • AUTOMATIC (rules 4, 5, 8, 15) — a verbatim text rewrite the reviewer can
    accept as a tracked change. Each finding carries ``original_text`` and
    ``replacement_text`` computed here in Python (no LLM "deciding").

  • VISUAL    (rules 1, 2, 6, 7) — a rule that is *broken* but has no text
    substitution (font size, line spacing, justification, keepNext). Flagged
    WITH A PAGE NUMBER for a human to confirm visually in the editor.

Layout rules that genuinely need a rendered page (3 margins, 9 line numbers,
12 widows, 13 footnote flow, 14 page numbering) and the semantic rules
(10 TOC, 11 TOA, 16 doc-id, 17 revisions, 18 overall) are handled elsewhere
(the vision pass / optional LLM) — they are all VISUAL.

Every finding here is shaped exactly like the dicts ``process_ai_job`` persists,
with a fully-populated ``location`` (page, paragraph, anchor_text, result,
change_class, engine).
"""

import re
from typing import Any

from src.services.ai_jobs.poc_rules import rule_meta, resolve_change_class
from src.utils.text_extractor import compute_rule_violations

_RULE_META = rule_meta()

# Abbreviations whose trailing period is NOT a sentence end — never treat a
# missing space after these as a period-spacing violation.
_ABBREVIATIONS = {
    "mr", "mrs", "ms", "dr", "prof", "hon", "st", "mt", "no", "nos", "vs", "v",
    "inc", "ltd", "co", "corp", "llc", "llp", "jr", "sr", "vol", "ed", "eds",
    "fig", "figs", "p", "pp", "para", "paras", "cf", "id", "al", "dept", "ave",
    "blvd", "rd", "ste", "div", "art", "sec", "ch", "ex",
}

# Doubled words that are virtually always typos (articles/prepositions/conjunctions).
# Conservative on purpose — "had had", "that that" are valid English, so excluded.
_DOUBLE_SAFE = {
    "the", "a", "an", "of", "to", "and", "in", "for", "with", "on", "at", "by",
    "is", "was", "be", "or", "as", "that", "this", "it",
}

# ── regexes ───────────────────────────────────────────────────────────────────
# Sentence merge: lowercase/digit + '.' + Capitalised word, with no space.
_PERIOD_RE = re.compile(r"([A-Za-z0-9]*[a-z0-9])\.([A-Z][a-z]+)")
# Section/paragraph symbol immediately followed by an identifier (no space).
_SECTION_RE = re.compile(r"([§¶]+)([0-9A-Za-z][0-9A-Za-z.,()\-]*)")
# Space(s) before a punctuation mark — capture the whole preceding word so the
# anchor is specific (a one-char anchor like "t ;" would match all over the doc).
_SPACE_BEFORE_PUNCT_RE = re.compile(r"([\w'’\-]+)\s+([,;:.!?])")
# Missing space after a comma/semicolon/colon between two words (require letters
# on both sides so digits — "1,000", "12:30" — are never touched).
_MISSING_SPACE_RE = re.compile(r"([A-Za-z]+[,;:])([A-Za-z]+)")
# Straight / curly double-quote pairs (single-line, bounded).
_STRAIGHT_PAIR_RE = re.compile(r'"([^"\n]{0,200}?)"')
_CURLY_PAIR_RE = re.compile(r"“([^“”\n]{0,200}?)”")


def _page_for(paragraph, page_map: list[int]) -> int | None:
    if isinstance(paragraph, int) and 0 <= paragraph < len(page_map):
        return page_map[paragraph]
    return None


def _finding(
    rule_id: int,
    *,
    description: str,
    suggested_fix: str,
    paragraph=None,
    anchor: str | None = None,
    original: str | None = None,
    replacement: str | None = None,
    page: int | None = None,
    confidence: float = 0.97,
) -> dict:
    """Build a QCFinding-shaped dict with a fully-populated ``location``."""
    meta = _RULE_META.get(rule_id, {})
    change_class = resolve_change_class(rule_id, original, replacement)
    # POC result: automatic fixes and detected property violations are 'fail';
    # the warn-only rules (3/9/14) are emitted elsewhere.
    result = "fail"
    return {
        "rule_id": rule_id,
        "rule_name": meta.get("name", f"Rule {rule_id}"),
        "track": meta.get("track", 1),
        "type": meta.get("type", "formatting"),
        "severity": meta.get("severity", "major"),
        "change_class": change_class,
        "confidence": confidence,
        "location": {
            "page": page,
            "paragraph": paragraph,
            "anchor_text": (anchor[:160] if anchor else None),
            "result": result,
            "change_class": change_class,
            "engine": "deterministic",
        },
        "description": description,
        "original_text": original,
        "replacement_text": replacement,
        "suggested_fix": suggested_fix,
    }


def _iter_text_paragraphs(paras: list[dict]):
    """Yield (index, raw_text) for every non-empty paragraph. Automatic text
    fixes apply anywhere (body, headings, captions); the regexes are precise
    enough that ALL-CAPS title blocks don't match the prose patterns."""
    for p in paras:
        if not (p.get("text") or "").strip():
            continue
        yield p.get("index"), p.get("text") or ""


# ── AUTOMATIC fixers (produce original → replacement) ───────────────────────────

def _fix_period_spacing(paras, page_map) -> list[dict]:
    out: list[dict] = []
    for idx, text in _iter_text_paragraphs(paras):
        for m in _PERIOD_RE.finditer(text):
            before, after = m.group(1), m.group(2)
            if before.lower() in _ABBREVIATIONS:
                continue
            original = m.group(0)
            replacement = f"{before}.  {after}"
            out.append(_finding(
                5,
                paragraph=idx,
                page=_page_for(idx, page_map),
                anchor=original,
                original=original,
                replacement=replacement,
                description=(
                    f"Missing space after a sentence period (\"{original}\"). "
                    "GRSS style uses two spaces after a period in body text."
                ),
                suggested_fix="Insert two spaces after the period.",
            ))
    return out


def _fix_section_symbol(paras, page_map) -> list[dict]:
    out: list[dict] = []
    for idx, text in _iter_text_paragraphs(paras):
        for m in _SECTION_RE.finditer(text):
            sym, rest = m.group(1), m.group(2)
            original = m.group(0)
            replacement = f"{sym} {rest}"
            out.append(_finding(
                8,
                paragraph=idx,
                page=_page_for(idx, page_map),
                anchor=original,
                original=original,
                replacement=replacement,
                description=(
                    f"No space after the section symbol (\"{original}\"). "
                    "Use one space (e.g. “§ 1234”)."
                ),
                suggested_fix="Insert one space between the symbol and the number.",
            ))
    return out


def _fix_grammar_mechanics(paras, page_map) -> list[dict]:
    out: list[dict] = []
    for idx, text in _iter_text_paragraphs(paras):
        page = _page_for(idx, page_map)
        seen: set[tuple] = set()

        def add(original, replacement, desc, fix):
            key = (idx, original, replacement)
            if original == replacement or key in seen:
                return
            seen.add(key)
            out.append(_finding(
                15, paragraph=idx, page=page, anchor=original,
                original=original, replacement=replacement,
                description=desc, suggested_fix=fix, confidence=0.95,
            ))

        for m in _SPACE_BEFORE_PUNCT_RE.finditer(text):
            original = m.group(0)
            replacement = f"{m.group(1)}{m.group(2)}"
            add(original, replacement,
                f"Space before punctuation (\"{original.strip()}\").",
                "Remove the space before the punctuation mark.")

        for m in _MISSING_SPACE_RE.finditer(text):
            original = m.group(0)
            replacement = f"{m.group(1)} {m.group(2)}"
            add(original, replacement,
                f"Missing space after punctuation (\"{original}\").",
                "Add a space after the comma/semicolon/colon.")

        for m in re.finditer(r"\b(\w+)(\s+)(\1)\b", text, flags=re.IGNORECASE):
            first, gap, second = m.group(1), m.group(2), m.group(3)
            if first.lower() not in _DOUBLE_SAFE:
                continue
            original = m.group(0)
            replacement = first  # keep first occurrence (and its case)
            add(original, replacement,
                f"Repeated word (\"{first} {second}\").",
                "Remove the duplicated word.")
    return out


def _document_quote_style(paras) -> str | None:
    """Majority double-quote style across the document, or None if only one
    style is used (already consistent → nothing to normalise)."""
    straight = curly = 0
    for p in paras:
        t = p.get("text") or ""
        straight += t.count('"')
        curly += t.count("“") + t.count("”")
    if straight and curly:
        return "curly" if curly >= straight else "straight"
    return None  # consistent (or no quotes) — no rule-4 finding


def _fix_quotes(paras, page_map) -> list[dict]:
    target = _document_quote_style(paras)
    if not target:
        return []
    out: list[dict] = []
    for idx, text in _iter_text_paragraphs(paras):
        page = _page_for(idx, page_map)
        if target == "curly":
            # Convert straight pairs "…" → “…”
            for m in _STRAIGHT_PAIR_RE.finditer(text):
                inner = m.group(1)
                if '"' in inner:
                    continue
                original = m.group(0)
                replacement = f"“{inner}”"
                out.append(_finding(
                    4, paragraph=idx, page=page, anchor=original,
                    original=original, replacement=replacement,
                    description="Straight quotes used where the document is mostly curly.",
                    suggested_fix="Use curly quotes consistently.",
                    confidence=0.9,
                ))
        else:
            for m in _CURLY_PAIR_RE.finditer(text):
                inner = m.group(1)
                original = m.group(0)
                replacement = f'"{inner}"'
                out.append(_finding(
                    4, paragraph=idx, page=page, anchor=original,
                    original=original, replacement=replacement,
                    description="Curly quotes used where the document is mostly straight.",
                    suggested_fix="Use straight quotes consistently.",
                    confidence=0.9,
                ))
    return out


# ── VISUAL detectors (flag-only, page-numbered) ─────────────────────────────────

def _visual_findings(structured, page_map) -> list[dict]:
    """Rules 1, 2, 6, 7 — XML-detectable property violations. Reuses the proven
    deterministic detection in ``compute_rule_violations`` and turns each entry
    into a page-numbered visual finding."""
    try:
        pre = compute_rule_violations(structured)
    except Exception:
        return []
    viol = pre.get("violations", {})
    paras = (structured or {}).get("paragraphs", []) or []
    out: list[dict] = []

    # footnote id → page of the body paragraph that references it.
    fn_ref_page: dict[str, int] = {}
    for p in paras:
        pg = _page_for(p.get("index"), page_map)
        if pg is None:
            continue
        for rid in p.get("footnote_refs", []) or []:
            fn_ref_page.setdefault(str(rid), pg)

    for v in viol.get("rule_1_footnote_font", []) or []:
        fn_page = fn_ref_page.get(str(v.get("footnote_id")))
        out.append(_finding(
            1, paragraph=None, page=fn_page, anchor=v.get("snippet"),
            description=(
                f"Footnote font size {v.get('got_pt')}pt; with a {v.get('body_size_pt')}pt "
                f"body, footnotes should be {v.get('expected_pt')}pt."
            ),
            suggested_fix=f"Set the footnote font size to {v.get('expected_pt')}pt.",
        ))
    for v in viol.get("rule_1_body_font", []) or []:
        idx = v.get("paragraph")
        out.append(_finding(
            1, paragraph=idx, page=_page_for(idx, page_map), anchor=v.get("snippet"),
            description=(
                f"Paragraph {idx} uses {v.get('got_pt')}pt body text; the document body is "
                f"{v.get('expected_pt')}pt."
            ),
            suggested_fix=f"Set the paragraph font size to {v.get('expected_pt')}pt.",
        ))
    for v in viol.get("rule_2_line_spacing", []) or []:
        idx = v.get("paragraph")
        out.append(_finding(
            2, paragraph=idx, page=_page_for(idx, page_map), anchor=v.get("snippet"),
            description=(
                f"Paragraph {idx} line spacing is {v.get('got_line')} ({v.get('line_rule')}); "
                "body text should be exactly 24pt (line=480)."
            ),
            suggested_fix="Set line spacing to exactly 24pt (line=480, lineRule=auto).",
        ))
    for v in viol.get("rule_6_justification", []) or []:
        idx = v.get("paragraph")
        out.append(_finding(
            6, paragraph=idx, page=_page_for(idx, page_map), anchor=v.get("snippet"),
            description=(
                f"Paragraph {idx} is {v.get('got_alignment')}-aligned; body text in this "
                "document is fully justified."
            ),
            suggested_fix="Set paragraph alignment to fully justified.",
        ))
    for v in viol.get("rule_7_orphan_heading", []) or []:
        idx = v.get("paragraph")
        out.append(_finding(
            7, paragraph=idx, page=_page_for(idx, page_map), anchor=v.get("snippet"),
            description=(
                f"Section heading at paragraph {idx} has 'keep with next' disabled — risk of "
                "an orphan heading at a page break."
            ),
            suggested_fix="Enable 'Keep with next' on this heading paragraph.",
        ))
    return out


def analyze(structured: dict[str, Any], page_map: list[int] | None = None) -> list[dict]:
    """Run the full deterministic engine. Returns QCFinding-shaped finding dicts
    (automatic text fixes + page-numbered visual flags). Safe on empty input."""
    paras = (structured or {}).get("paragraphs", []) or []
    page_map = page_map or []
    findings: list[dict] = []
    # AUTOMATIC (text rewrites)
    findings += _fix_period_spacing(paras, page_map)
    findings += _fix_section_symbol(paras, page_map)
    findings += _fix_grammar_mechanics(paras, page_map)
    findings += _fix_quotes(paras, page_map)
    # VISUAL (page-numbered flags)
    findings += _visual_findings(structured, page_map)
    return findings


# Rule ids this engine owns authoritatively — used by process_ai_job to drop any
# overlapping LLM findings so the deterministic result always wins.
ENGINE_OWNED_RULES = {1, 2, 4, 5, 6, 7, 8, 15}
