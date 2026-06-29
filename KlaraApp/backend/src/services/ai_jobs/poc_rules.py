"""Canonical definition of the 18-rule Klara GRSS "Checklist for Formatting
Pleadings" used by the POC AI engine.

This is the single source of truth for the rule set. The AI-engine metadata map
(`_RULE_META` in ai_job_service.py) is derived from this list, and the
`GET /config/poc-rules` endpoint serves it so the Rules dashboard can display
and let reviewers verify the rules manually instead of relying on hard-coded
front-end placeholders.

`detection` describes HOW the engine evaluates each rule:
  - "Automated"  → deterministic detection from the .docx XML (no LLM needed)
  - "AI/LLM"     → evaluated by the language model
  - "Manual"     → cannot be verified from the XML; emitted as a warning for a
                   human to confirm visually (margins, line numbers, page numbers)

`change_class` describes WHAT the reviewer can do with a finding — the axis the
review UI splits on (the "Automatic" vs "Visual" tabs):
  - "automatic"  → the engine can deterministically rewrite the offending text
                   and show it as a tracked change (period/section-symbol
                   spacing, quote consistency, grammar/mechanics). Computed in
                   pure Python — no LLM "deciding".
  - "visual"     → the rule is *broken* but there is no verbatim text
                   substitution to apply (font size, line spacing, justification,
                   margins, page numbering, …). The engine flags it WITH A PAGE
                   NUMBER for a human to confirm visually in the editor.
"""

# Human-readable track labels (mirrors the three AI-engine tracks in the proposal).
TRACK_LABELS = {
    1: "Track 1 — Formatting & Style",
    2: "Track 2 — Missing Information",
    3: "Track 3 — Business Logic",
}

# id, track, name, detail/standard, finding_type, severity, detection, change_class
POC_18_RULES: list[dict] = [
    # ---- Track 1 — Formatting & Style ----
    {"id": 1, "track": 1, "name": "Font consistency",
     "detail": "14pt body ⇒ 14pt footnotes; 12pt body ⇒ 10pt footnotes.",
     "type": "formatting", "severity": "critical", "detection": "Automated",
     "change_class": "visual"},
    {"id": 2, "track": 1, "name": "Paragraph & line spacing",
     "detail": "Body text exactly 24pt, 0 spaces before/after (except headings & indented quotes).",
     "type": "formatting", "severity": "critical", "detection": "Automated",
     "change_class": "visual"},
    {"id": 3, "track": 1, "name": "Margins",
     "detail": "Correct and consistent margins in every section.",
     "type": "formatting", "severity": "suggestion", "detection": "Manual",
     "change_class": "visual"},
    {"id": 4, "track": 1, "name": "Quotation marks consistency",
     "detail": "Consistent throughout (straight or curly), including footnotes.",
     "type": "consistency", "severity": "major", "detection": "Automated",
     "change_class": "automatic"},
    {"id": 5, "track": 1, "name": "Period spacing",
     "detail": "Two spaces after periods in body text.",
     "type": "formatting", "severity": "major", "detection": "Automated",
     "change_class": "automatic"},
    {"id": 6, "track": 1, "name": "Paragraph justification",
     "detail": "Consistent throughout the document, including footnotes.",
     "type": "formatting", "severity": "major", "detection": "Automated",
     "change_class": "visual"},
    {"id": 7, "track": 1, "name": "Heading orphan / keepNext",
     "detail": "No orphan titles; keep with next; space after ensures paragraph prints on the numbered line.",
     "type": "formatting", "severity": "major", "detection": "Automated",
     "change_class": "visual"},
    {"id": 8, "track": 1, "name": "Section symbol spacing",
     "detail": "One space after the section symbol (§ 1234, not §1234).",
     "type": "formatting", "severity": "major", "detection": "Automated",
     "change_class": "automatic"},
    {"id": 9, "track": 1, "name": "Line numbers",
     "detail": "Lined up with text throughout (except single-spaced headings and indented quotes).",
     "type": "formatting", "severity": "suggestion", "detection": "Manual",
     "change_class": "visual"},
    # ---- Track 2 — Missing Information ----
    {"id": 10, "track": 2, "name": "TOC completeness",
     "detail": "No full paragraphs; case names italicized; roman numerals; consistent font/placement.",
     "type": "consistency", "severity": "suggestion", "detection": "AI/LLM",
     "change_class": "visual"},
    {"id": 11, "track": 2, "name": "TOA completeness",
     "detail": "Case name italic on first line; cite non-italic indented ¼ inch; alphabetical order.",
     "type": "consistency", "severity": "suggestion", "detection": "AI/LLM",
     "change_class": "visual"},
    {"id": 12, "track": 2, "name": "Widows & orphans",
     "detail": "No widows/orphans; no broken tables; date and signature block kept together.",
     "type": "formatting", "severity": "suggestion", "detection": "AI/LLM",
     "change_class": "visual"},
    {"id": 13, "track": 2, "name": "Footnote flow",
     "detail": "Footnotes do not flow to more than one additional page.",
     "type": "formatting", "severity": "suggestion", "detection": "AI/LLM",
     "change_class": "visual"},
    {"id": 14, "track": 2, "name": "Page numbering",
     "detail": "First page of body has no number; subsequent pages numbered correctly.",
     "type": "metadata", "severity": "suggestion", "detection": "Manual",
     "change_class": "visual"},
    # ---- Track 3 — Business Logic ----
    {"id": 15, "track": 3, "name": "Spelling & grammar",
     "detail": "Spell and grammar checked; period spacing verified.",
     "type": "spelling", "severity": "minor", "detection": "Automated",
     "change_class": "automatic"},
    {"id": 16, "track": 3, "name": "Document ID",
     "detail": "Number only — no label text.",
     "type": "metadata", "severity": "minor", "detection": "AI/LLM",
     "change_class": "visual"},
    {"id": 17, "track": 3, "name": "Revisions accuracy",
     "detail": "All inserts and deletions completed correctly and accurately.",
     "type": "consistency", "severity": "minor", "detection": "AI/LLM",
     "change_class": "visual"},
    {"id": 18, "track": 3, "name": "Overall consistency",
     "detail": "Fonts, paragraphs, margins, and quotes consistent throughout.",
     "type": "consistency", "severity": "minor", "detection": "AI/LLM",
     "change_class": "visual"},
]


# Rules that cannot be verified from the extracted .docx text (margins, line
# numbers, footer page numbers). The engine still evaluates them automatically,
# but the honest POC result is a "warning" for a human to confirm visually.
# Every other detected violation is a "fail". Rules with no finding = "pass".
WARNING_RULES = {3, 9, 14}

RULE_NAME = {r["id"]: r["name"] for r in POC_18_RULES}

# The two review classes (see the module docstring). ``automatic`` rules are the
# only ones the engine rewrites verbatim; everything else is ``visual``.
AUTOMATIC_RULES = {r["id"] for r in POC_18_RULES if r["change_class"] == "automatic"}
VISUAL_RULES = {r["id"] for r in POC_18_RULES if r["change_class"] == "visual"}
_RULE_CHANGE_CLASS = {r["id"]: r["change_class"] for r in POC_18_RULES}


def rule_change_class(rule_id) -> str:
    """The review class for a rule_id: 'automatic' (deterministic text rewrite)
    or 'visual' (flag for human visual check). Unknown ids default to 'visual'
    — a finding with no concrete text replacement belongs in the visual tab."""
    return _RULE_CHANGE_CLASS.get(rule_id, "visual")


def resolve_change_class(rule_id, original_text=None, replacement_text=None) -> str:
    """Final change-class for a *finding*: a rule is only 'automatic' when it is
    an automatic-class rule AND actually carries a verbatim text substitution to
    apply. A flagged automatic-rule with no replacement falls back to 'visual'
    so the reviewer still sees it (with a page number) instead of an un-actionable
    'Accept' button."""
    base = rule_change_class(rule_id)
    if base != "automatic":
        return "visual"
    has_fix = bool(original_text) and bool(replacement_text) and original_text != replacement_text
    return "automatic" if has_fix else "visual"


def poc_result(rule_id) -> str:
    """Strict POC classification for a finding: 'warning' for the
    unverifiable-from-text rules, 'fail' for every other detected violation.
    (Absence of a finding for a rule means 'pass'.)"""
    return "warning" if rule_id in WARNING_RULES else "fail"


# Rendered-layout rules a text model / XML parse cannot reliably verify. These
# are evaluated by the gpt-4o VISION model against rendered page images instead.
VISION_RULES = {3, 9, 12, 13, 14}

VISION_SYSTEM_PROMPT = """You are the Klara GRSS QC vision inspector. You are given
rendered page images of a legal pleading and must evaluate ONLY the following
layout rules — the ones that can only be judged from the rendered page, not from
the document's text:

  Rule 3  — Margins: consistent, correct margins on every page (≈1 inch; pleading
            paper line-numbered left margin where applicable).
  Rule 9  — Line numbers: where the format uses numbered lines, the numbers line
            up with the body text rows (skip if the court format has no line numbers).
  Rule 12 — Widows & orphans: no single line of a paragraph stranded at the top or
            bottom of a page; signature block and date kept together; no broken tables.
  Rule 13 — Footnote flow: a footnote does not spill across more than one extra page.
  Rule 14 — Page numbering: first page of the body is unnumbered; subsequent pages
            are numbered correctly in the footer.

For EACH of these five rules return a verdict:
  - "pass"    — the page images clearly satisfy the rule.
  - "fail"    — the page images clearly violate the rule (describe exactly what/where).
  - "warning" — you cannot determine it confidently from the images (say why).

Be conservative: prefer "pass" or "warning" over "fail" unless the violation is
visible. Reference the page number where relevant. Do NOT evaluate any other
rules (font, quotes, spacing, §, spelling, etc.) — those are handled elsewhere.

Return STRICT JSON (no markdown):
{
  "findings": [
    { "rule_id": 3|9|12|13|14, "result": "pass"|"fail"|"warning",
      "page": <int|null>, "description": "<specific observation>",
      "suggested_fix": "<short imperative fix, or null>" }
  ]
}
Include one entry per rule you assessed."""


VISION_USER_PROMPT = (
    "Evaluate the attached rendered pages of this pleading against rules 3, 9, 12, "
    "13, and 14 only. Return the strict-JSON object defined in the system prompt, "
    "with one finding per rule you assessed (pass/fail/warning)."
)


def rule_meta() -> dict[int, dict]:
    """Derive the AI-engine metadata map (rule_id → name/track/type/severity)
    from the canonical rule list, keeping a single source of truth."""
    return {
        r["id"]: {
            "name": r["name"],
            "track": r["track"],
            "type": r["type"],
            "severity": r["severity"],
            "change_class": r["change_class"],
        }
        for r in POC_18_RULES
    }


def rules_for_api() -> list[dict]:
    """Serialize the 18 rules for the Rules dashboard, including the track label."""
    return [{**r, "track_label": TRACK_LABELS[r["track"]]} for r in POC_18_RULES]
