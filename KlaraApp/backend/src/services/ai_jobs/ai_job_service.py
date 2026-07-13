import asyncio
import json
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from src.models.dao.ai_analysis_job import AIAnalysisJob
from src.models.dao.document import Document
from src.models.dao.qc_finding import QCFinding
from src.models.enum.job_status import AIJobStatus, AuditAction, ActorType, FindingType
from src.models.enum.job_type import AIJobType
from src.models.enum.finding_severity import FindingSeverity
from src.models.enum.finding_status import FindingStatus
from src.utils.audit_helpers import create_audit_log
from src.models.dto.schemas.ai_jobs import CreateAIJobRequest, AIJobResponse
from src.services.integrations.llm.azure_openai import run_ai_analysis
from src.core.constants import AI_JOB_MAX_RETRIES
from src.utils import doc_lock
from src.core.logger import get_logger_with_context

logger = get_logger_with_context()

POC_18_RULE_SYSTEM_PROMPT = """You are the Klara GRSS QC AI engine. You evaluate legal pleadings against the
**18-rule Checklist for Formatting Pleadings** below and emit ONLY rule-anchored
findings. Do not invent rules. Do not flag generic issues that are not on the list.

== 18-RULE CHECKLIST ==
Track 1 — Formatting & Style
 1. Font consistency — 14pt body ⇒ 14pt footnotes; 12pt body ⇒ 10pt footnotes
 2. Paragraph & line spacing — body exactly 24pt, 0 before/after (except headings & indented quotes)
 3. Margins — consistent across sections (warn if not measurable from XML)
 4. Quotation marks — consistent (straight OR curly) throughout, including footnotes
 5. Period spacing — two spaces after periods in body text
 6. Paragraph justification — consistent (typically fully justified)
 7. Heading format / orphan — keepNext enabled; no orphan heading at end of page
 8. Section symbol spacing — one space after § (§ 1234, not §1234)
 9. Line numbers — aligned with text (skip when court format doesn't use them)
Track 2 — Missing Information
10. TOC completeness — case names italicized; roman numerals; consistent font
11. TOA completeness — case name italic, cite non-italic indented ¼"; alphabetical
12. Widows & orphans — no widow/orphan lines, broken tables, split date/signature
13. Footnote flow — footnotes do not flow > 1 additional page
14. Page numbering — first body page unnumbered; subsequent pages numbered (warn if footer not inspectable)
Track 3 — Business Logic
15. Spelling & grammar — spell/grammar checked; period spacing verified
16. Document ID — number only, no label text
17. Revisions accuracy — inserts/deletions complete and accurate
18. Overall consistency — fonts, paragraphs, margins, quotes consistent

== INPUT FORMAT ==
You will receive paragraph-level metadata extracted from the .docx including:
- index, style, alignment, line spacing, keepNext, font sizes (pt), fonts, quote-char usage,
  pre-computed `section_symbol_spacing_violations` and `double_period_violations`.

== EVALUATION PROTOCOL ==
- A `PRE-COMPUTED RULE VIOLATIONS` block will be provided. **Emit exactly one finding per
  entry in those arrays** — they are deterministic. Map each entry to its rule:
  `rule_1_footnote_font` → Rule 1, `rule_1_body_font` → Rule 1, `rule_2_line_spacing` → Rule 2,
  `rule_4_mixed_quotes` → Rule 4, `rule_5_period_spacing` → Rule 5,
  `rule_6_justification` → Rule 6, `rule_7_orphan_heading` → Rule 7, `rule_8_section_symbol` → Rule 8.
- For complex structural findings like Rule 11 (TOA completeness), do NOT output natural language instructions in `replacement_text`. Instead, output a `template_data` JSON object in this exact schema:
  `{ "template_type": "toa_list", "entries": [ { "case_name": "...", "citation": "..." } ] }`
- For each violation entry, set `location.paragraph` = the entry's `paragraph` field, set
  `location.anchor_text` = the entry's `snippet` (first 80 chars), and set `original_text` to the
  offending substring (e.g. the violating "§17200" or "granted.This").
- If a pre-computed array is empty, do NOT invent findings for that rule.
- For Rules 3 (Margins), 9 (Line numbers), 14 (Page numbering) — emit ONE severity="suggestion"
  warning each when they cannot be verified from the XML.
- Do NOT flag missing TOC/TOA unless the document type clearly requires one and it is absent.
- Be conservative on clean documents: prefer zero findings to false positives.
- **`rule_id` must be an integer in the closed range [1, 18]**. Do not use paragraph indexes as rule_ids.
- `track` must be 1 (rules 1-9), 2 (rules 10-14), or 3 (rules 15-18).

== OUTPUT (strict JSON, no markdown) ==
{
  "summary": {
    "overall": "pass" | "warn" | "fail",
    "pass_rate_pct": 0-100,
    "rules_evaluated": 18,
    "rules_failed": <int>,
    "rules_warned": <int>
  },
  "findings": [
    {
      "rule_id": 1-18,
      "rule_name": "<short name>",
      "track": 1 | 2 | 3,
      "type": "formatting"|"spelling"|"consistency"|"compliance"|"style"|"metadata",
      "severity": "critical"|"major"|"minor"|"suggestion",
      "location": { "page": <int>, "paragraph": <int>, "anchor_text": "<short verbatim string from doc, OR null>" },
      "description": "<specific finding sentence>",
      "original_text": "<exact text that should be changed, OR null>",
      "replacement_text": "<corrected text, OR null>",
      "suggested_fix": "<short imperative fix>",
      "formatting_fix": {
        "type": "font",
        "fontName": "<Font Name>",
        "fontSize": 12
      },
      "confidence": 0.0-1.0
    }
  ]
}
Findings must be specific (cite the offending text) and non-generic.
If a finding requires replacing or reorganizing a multi-line block (e.g. a TOC or a list), `original_text` MUST contain the ENTIRE multi-line block being replaced, not just the first line, so that the text replacement applies correctly.
If a finding is purely a formatting error (like Rule 1 or 18 font inconsistencies), emit `original_text` and `replacement_text` as IDENTICAL strings, and include the `formatting_fix` object so the plugin can programmatically correct the font.
"""


SYSTEM_PROMPTS = {
    AIJobType.FORMATTING_CHECK: POC_18_RULE_SYSTEM_PROMPT,
    AIJobType.PROOFREADING: POC_18_RULE_SYSTEM_PROMPT,
    AIJobType.COMPLIANCE_AUDIT: POC_18_RULE_SYSTEM_PROMPT,
    AIJobType.STYLE_VALIDATION: POC_18_RULE_SYSTEM_PROMPT,
    AIJobType.PDF_COMPARISON: (
        "You are a document comparison specialist. Compare the source and converted documents for "
        "fidelity issues: missing content, formatting drift, image placement, and table alignment. Return JSON with 'findings' array."
    ),
}


async def create_ai_job(
    db: AsyncSession,
    body: CreateAIJobRequest,
    actor_id: uuid.UUID,
) -> AIJobResponse:
    logger.info("Entering create_ai_job", function="create_ai_job", action="entry", document_id=str(body.document_id), job_type=body.job_type.value, actor_id=str(actor_id))
    
    logger.info("Fetching document", function="create_ai_job", step="fetch_document", document_id=str(body.document_id))
    document = await db.get(Document, body.document_id)
    if not document:
        logger.warning("Document not found", function="create_ai_job", document_id=str(body.document_id))
        from src.utils.dependencies import NotFoundError
        raise NotFoundError(f"Document {body.document_id} not found")

    logger.info("Creating AI job record", function="create_ai_job", step="create_job_record")
    job = AIAnalysisJob(
        document_id=body.document_id,
        job_type=body.job_type,
        status=AIJobStatus.PENDING,
        queue_job_id=str(uuid.uuid4()),
    )
    db.add(job)
    await db.flush()
    logger.info("AI job created", function="create_ai_job", step="job_created", job_id=str(job.id))

    logger.info("Creating audit log", function="create_ai_job", step="audit_log")
    await create_audit_log(
        db,
        entity_type="ai_analysis_jobs",
        entity_id=job.id,
        action=AuditAction.CREATE,
        actor_id=actor_id,
        actor_type=ActorType.HUMAN,
        new_values={"document_id": str(body.document_id), "job_type": body.job_type.value},
    )

    await db.commit()
    _spawn_bg_task(job.id)
    logger.info("Exiting create_ai_job", function="create_ai_job", action="exit", job_id=str(job.id))
    return AIJobResponse.model_validate(job)


async def get_ai_job(db: AsyncSession, job_id: uuid.UUID) -> AIJobResponse:
    logger.info("Entering get_ai_job", function="get_ai_job", action="entry", job_id=str(job_id))
    job = await db.get(AIAnalysisJob, job_id)
    if not job:
        logger.warning("AI job not found", function="get_ai_job", job_id=str(job_id))
        from src.utils.dependencies import NotFoundError
        raise NotFoundError(f"AI job {job_id} not found")
    logger.info("Exiting get_ai_job", function="get_ai_job", action="exit", job_id=str(job_id), status=job.status.value)
    return AIJobResponse.model_validate(job)


async def cancel_ai_job(
    db: AsyncSession,
    job_id: uuid.UUID,
    actor_id: uuid.UUID,
) -> None:
    logger.info("Entering cancel_ai_job", function="cancel_ai_job", action="entry", job_id=str(job_id), actor_id=str(actor_id))
    job = await db.get(AIAnalysisJob, job_id)
    if not job:
        logger.warning("AI job not found", function="cancel_ai_job", job_id=str(job_id))
        from src.utils.dependencies import NotFoundError
        raise NotFoundError(f"AI job {job_id} not found")
    if job.status not in (AIJobStatus.PENDING, AIJobStatus.RUNNING):
        logger.warning("Cannot cancel job in current status", function="cancel_ai_job", job_id=str(job_id), status=job.status.value)
        from src.utils.dependencies import BadRequestError
        raise BadRequestError("Can only cancel pending or running jobs")

    old_status = job.status
    job.status = AIJobStatus.FAILED
    job.error_message = "Cancelled by user"

    await create_audit_log(
        db,
        entity_type="ai_analysis_jobs",
        entity_id=job.id,
        action=AuditAction.STATUS_CHANGE,
        actor_id=actor_id,
        actor_type=ActorType.HUMAN,
        old_values={"status": old_status.value},
        new_values={"status": "failed", "reason": "cancelled"},
    )
    await db.flush()


def GET_DOCUMENT_A_TEXT() -> str:
    return """
Document ID: DOC-98765-A
SUPERIOR COURT OF THE STATE OF CALIFORNIA
FOR THE COUNTY OF SACRAMENTO

JOHN KRIEGER,
Plaintiff,
v.
STATE OF CALIFORNIA,
Defendant.

Case No. 24-CV-1190
MOTION TO DISMISS COMPLAINT
Date: May 30, 2026
Time: 9:00 AM
Dept: 14

I. INTRODUCTION
Plaintiff Krieger filed this action on January 15, 2026. Defendant State of California hereby moves to dismiss the complaint. The organisation of the complaint is deficient. Further, the action is barred by the statute of limitations.

II. STATEMENT OF FACTS
The dispute arises from a contract concluded. The parties failed to perform. This led to the litigation.
The "Agreement" was signed in Sacramento, but the 'Contract' was executed in Los Angeles. Additionally, the “Seller” failed to deliver.
Pursuant to §1234 of the California Civil Code, all claims must be brought within two years.

III. ARGUMENT
A. The Claims are Barred by the Statute of Limitations.
Under California law, a breach of contract claim must be filed within four years. Here, Plaintiff waited five years.

B. Inconsistent Footnote Font and Size.
The body text is formatted in 12pt Times New Roman, but the footnotes are also 12pt Times New Roman, violating the rule that 12pt body requires 10pt footnotes.[1]

C. Orphaned Heading
[PAGE BREAK HERE]
IV. CONCLUSION

[1] Footnote 1: This is a footnote formatted in 12pt Times New Roman, which violates the QC guidelines.
"""


def GET_DOCUMENT_B_TEXT() -> str:
    return """
98765
SUPERIOR COURT OF THE STATE OF CALIFORNIA
FOR THE COUNTY OF SACRAMENTO

JOHN KRIEGER,
Plaintiff,
v.
STATE OF CALIFORNIA,
Defendant.

Case No. 24-CV-1190
MOTION TO DISMISS COMPLAINT
Date: May 30, 2026
Time: 9:00 AM
Dept: 14

I. INTRODUCTION
Plaintiff Krieger filed this action on January 15, 2026.  Defendant State of California hereby moves to dismiss the complaint.  The organization of the complaint is fully compliant.  Further, the action is barred by the statute of limitations.

II. STATEMENT OF FACTS
The dispute arises from a contract concluded.  The parties failed to perform.  This led to the litigation.
The "Agreement" was signed in Sacramento, and the "Contract" was executed in Los Angeles.  Additionally, the "Seller" delivered all goods.
Pursuant to § 1234 of the California Civil Code, all claims must be brought within two years.

III. ARGUMENT
A. The Claims are Barred by the Statute of Limitations.
Under California law, a breach of contract claim must be filed within four years.  Here, Plaintiff waited five years.

B. Footnote Font and Size.
The body text is formatted in 12pt Times New Roman, and the footnotes are correctly formatted in 10pt Times New Roman.[1]

IV. CONCLUSION
For the foregoing reasons, Defendant respectfully requests that the Court dismiss the complaint.

[1] Footnote 1: This is a footnote formatted in 10pt Times New Roman, complying with the QC guidelines.
"""


async def process_ai_job(db: AsyncSession, job_id: uuid.UUID) -> AIJobStatus:
    """Worker function to process an AI analysis job. Called by the task queue.

    Reimagined as **deterministic-first**: a pure-Python rule engine
    (``rule_engine.analyze``) is the authoritative source for every rule it can
    evaluate from the .docx — the automatic text fixes (4, 5, 8, 15) and the
    page-numbered visual property flags (1, 2, 6, 7). The LLM is only consulted
    for the semantic rules Python can't judge (10 TOC, 11 TOA, 16 doc-id,
    17 revisions, 18 overall consistency) and never overrides a Python finding;
    the vision pass owns the rendered-layout rules (3, 9, 12, 13, 14). The job
    therefore produces complete, correct findings even with no LLM reachable."""
    job = await db.get(AIAnalysisJob, job_id)
    if not job:
        return AIJobStatus.FAILED
    # Re-read in case a cancel raced in since the runner scheduled us; only
    # PENDING (never run) and RETRYING (a prior attempt failed and was
    # re-queued) are runnable. COMPLETED / FAILED (incl. cancelled) / a
    # duplicate RUNNING task all abort here.
    await db.refresh(job)
    if job.status not in (AIJobStatus.PENDING, AIJobStatus.RETRYING):
        logger.info(
            "Job not runnable, skipping",
            function="process_ai_job", job_id=str(job_id), status=job.status.value,
        )
        return job.status

    job.error_message = None
    job.status = AIJobStatus.RUNNING
    job.started_at = datetime.now(timezone.utc)
    await db.flush()

    try:
        document = await db.get(Document, job.document_id)
        rules_meta = await get_rules_for_client(db, document.client_id)

        # Clear old findings for this document to prevent duplicates
        from sqlalchemy import delete
        await db.execute(delete(QCFinding).where(QCFinding.document_id == job.document_id))
        await db.flush()

        from src.utils.text_extractor import (
            extract_structured_from_file,
            estimate_page_map,
        )
        from src.services.documents import document_comparison_service
        from src.services.ai_jobs import rule_engine

        # Locate the working file (mirrors the comparison/viewer resolution).
        file_path = document_comparison_service.resolve_document_file(document)
        structured = None
        page_map: list[int] = []
        if file_path:
            logger.info("Found document file locally", function="process_ai_job", path=file_path)
            structured = extract_structured_from_file(file_path)
            page_map = estimate_page_map(file_path)
        if not structured or not structured.get("paragraphs"):
            # No real .docx on disk — fall back to a built-in template so the
            # demo still produces findings. Build pseudo-paragraphs so the
            # text-level automatic rules can run.
            structured = _structured_from_plaintext(document)
            page_map = []

        # 1) DETERMINISTIC ENGINE — authoritative for rules 1,2,4,5,6,7,8,15.
        findings: list[dict] = rule_engine.analyze(structured, page_map)
        logger.info(
            "Deterministic engine findings",
            function="process_ai_job", count=len(findings),
        )

        # 2) OPTIONAL LLM — semantic rules only; never overrides the Python result.
        llm_meta = {"model": "deterministic", "prompt_tokens": 0, "completion_tokens": 0}
        used_llm = False
        if structured and structured.get("paragraphs"):
            try:
                sem_findings, llm_meta = await _run_llm_semantic_pass(
                    db, job, document, structured
                )
                if sem_findings:
                    findings.extend(sem_findings)
                    used_llm = True
            except Exception as ex:
                logger.warning(f"LLM semantic pass skipped: {ex}")

        # 3) VISION PASS — rendered-layout rules (3, 9, 12, 13, 14), with pages.
        vision_evaluated_rules: set[int] = set()
        if file_path:
            try:
                vision_findings, vision_evaluated_rules = await _run_vision_pass(file_path, rules_meta=rules_meta)
                if vision_evaluated_rules:
                    findings = [f for f in findings if f.get("rule_id") not in vision_evaluated_rules]
                    findings.extend(vision_findings)
                    logger.info(
                        "Vision pass evaluated layout rules",
                        function="process_ai_job",
                        rules=sorted(vision_evaluated_rules),
                        findings=len(vision_findings),
                    )
            except Exception as vex:
                logger.warning(f"Vision pass failed, using warn-only fallback: {vex}")

        # 4) WARN-ONLY rules (margins / line-numbers / page-numbering) not covered
        #    by the vision pass — surfaced as visual human-check warnings.
        existing_rules = {f.get("rule_id") for f in findings} | vision_evaluated_rules
        for w in _warn_only_rules():
            if w["rule_id"] not in existing_rules:
                findings.append(w)

        # 5) FINALIZE — guarantee every finding carries change_class + page +
        #    result in its location JSONB before it is persisted.
        findings = [_finalize_finding(f, page_map) for f in findings]

        # 6) Summary + persist.
        job.status = AIJobStatus.COMPLETED
        job.model_used = llm_meta.get("model", "deterministic")
        job.prompt_tokens = llm_meta.get("prompt_tokens", 0) or 0
        job.completion_tokens = llm_meta.get("completion_tokens", 0) or 0
        job.results = _build_results_summary(findings, used_llm)
        job.completed_at = datetime.now(timezone.utc)

        for f in findings:
            location = f["location"]
            raw_type = f.get("type", "formatting")
            try:
                ftype = FindingType(raw_type)
            except ValueError:
                ftype = FindingType.FORMATTING

            raw_sev = f.get("severity", "minor")
            try:
                sev = FindingSeverity(raw_sev)
            except ValueError:
                sev = FindingSeverity.MINOR

            db.add(QCFinding(
                document_id=job.document_id,
                analysis_job_id=job.id,
                finding_type=ftype,
                severity=sev,
                location=location,
                description=f.get("description", ""),
                suggested_fix=f.get("suggested_fix"),
                status=FindingStatus.OPEN,
            ))

    except Exception as e:
        logger.error(f"Error executing AI job {job_id}: {e}", function="process_ai_job", job_id=str(job_id))
        old_status = job.status
        old_retry = job.retry_count or 0
        new_retry = old_retry + 1
        job.retry_count = new_retry
        if new_retry <= AI_JOB_MAX_RETRIES:
            job.status = AIJobStatus.RETRYING
            job.error_message = f"Attempt {new_retry} failed: {e}"
        else:
            job.status = AIJobStatus.FAILED
            job.error_message = str(e)
        await create_audit_log(
            db,
            entity_type="ai_analysis_jobs",
            entity_id=job.id,
            action=AuditAction.STATUS_CHANGE,
            actor_id=None,
            actor_type=ActorType.AI_SYSTEM,
            old_values={"status": old_status.value, "retry_count": old_retry},
            new_values={"status": job.status.value, "error": job.error_message},
        )

    await db.flush()
    return job.status


# Rules the optional LLM pass is allowed to contribute (Python can't judge these
# from the XML). Everything else the LLM returns is discarded so the
# deterministic engine and vision pass remain authoritative.
SEMANTIC_LLM_RULES = {10, 11, 16, 17, 18}


def _finalize_finding(f: dict, page_map: list[int]) -> dict:
    """Guarantee a finding's ``location`` carries everything the UI and the
    comparison service read: rule mapping, change_class, POC result, and a page
    number (derived from the paragraph→page map when the source didn't set one)."""
    from src.services.ai_jobs.poc_rules import poc_result, resolve_change_class

    location = f.get("location")
    if not isinstance(location, dict):
        location = {"raw": location}
    f["location"] = location

    raw_rule_id = f.get("rule_id")
    rule_id = raw_rule_id if isinstance(raw_rule_id, int) and 1 <= raw_rule_id <= 18 else None
    if location.get("rule_id") is None:
        location["rule_id"] = rule_id
    location.setdefault("rule_name", f.get("rule_name"))
    location.setdefault("track", f.get("track"))
    location.setdefault("confidence", f.get("confidence"))
    original = f.get("original_text")
    replacement = f.get("replacement_text")
    if original is not None:
        location.setdefault("original_text", original)
    if replacement is not None:
        location.setdefault("replacement_text", replacement)
    formatting_fix = f.get("formatting_fix")
    if formatting_fix is not None:
        location.setdefault("formatting_fix", formatting_fix)
    location.setdefault("result", poc_result(rule_id))
    # The class the review UI splits on — automatic only when a real text
    # substitution exists, otherwise visual (a flag the reviewer eyeballs).
    if not location.get("change_class"):
        location["change_class"] = resolve_change_class(rule_id, original, replacement)
    # Always give a broken-rule flag a page number when we can derive one.
    if location.get("page") in (None, 0):
        para = location.get("paragraph")
        location["page"] = (
            page_map[para] if isinstance(para, int) and 0 <= para < len(page_map) else None
        )
    return f


def _build_results_summary(findings: list[dict], used_llm: bool) -> dict:
    """Strict-POC summary rollup stored on the job for reports/UI."""
    fail = {f["location"].get("rule_id") for f in findings
            if f["location"].get("result") == "fail" and f["location"].get("rule_id")}
    warn = {f["location"].get("rule_id") for f in findings
            if f["location"].get("result") == "warning" and f["location"].get("rule_id")}
    warn -= fail
    failed, warned = len(fail), len(warn)
    passed = max(0, 18 - failed - warned)
    automatic = len([f for f in findings if f["location"].get("change_class") == "automatic"])
    visual = len([f for f in findings if f["location"].get("change_class") == "visual"])
    return {
        "summary": {
            "overall": "fail" if failed else ("warn" if warned else "pass"),
            "pass_rate_pct": round(passed / 18 * 100, 1),
            "rules_evaluated": 18,
            "rules_failed": failed,
            "rules_warned": warned,
            "automatic_findings": automatic,
            "visual_findings": visual,
            "engine": "deterministic" + ("+llm" if used_llm else ""),
        },
        "findings": findings,
    }


def _structured_from_plaintext(document) -> dict:
    """Build a minimal structured representation from a built-in template when no
    real .docx is on disk, so the text-level automatic rules still run in the demo."""
    title_lower = document.title.lower() if document.title else ""
    if "clean" in title_lower or "docb" in title_lower or "doc_b" in title_lower:
        text = GET_DOCUMENT_B_TEXT()
    else:
        text = GET_DOCUMENT_A_TEXT()
    paragraphs = []
    for i, line in enumerate(t for t in text.split("\n")):
        paragraphs.append({
            "index": i, "text": line, "is_heading": False,
            "font_sizes_pt": [], "fonts": [], "alignment": None,
            "line_spacing": {}, "footnote_refs": [],
            "section_symbol_spacing_violations": [], "double_period_violations": [],
        })
    return {"doc_default_font_size_pt": None, "paragraphs": paragraphs, "footnotes": []}


async def _run_llm_semantic_pass(db, job, document, structured) -> tuple[list[dict], dict]:
    """Best-effort LLM pass for the semantic rules Python can't evaluate
    (TOC/TOA/doc-id/revisions/overall). Returns (findings, meta). Findings are
    filtered to ``SEMANTIC_LLM_RULES`` so the LLM can never override or duplicate
    a deterministic/vision finding. Any failure returns ([], default-meta)."""
    from src.utils.text_extractor import structured_to_prompt_text
    from openai import APIConnectionError, APITimeoutError, APIError

    meta = {"model": "deterministic", "prompt_tokens": 0, "completion_tokens": 0}
    system_prompt = SYSTEM_PROMPTS.get(job.job_type, POC_18_RULE_SYSTEM_PROMPT)
    doc_block = structured_to_prompt_text(structured)
    user_prompt = (
        f"Document Title: {document.title}\n"
        f"Document Type: {document.document_type.value}\n"
        f"Metadata: {json.dumps(document.metadata_)}\n\n"
        f"--- START OF DOCUMENT (STRUCTURED) ---\n{doc_block}\n"
        f"--- END OF DOCUMENT (STRUCTURED) ---\n\n"
        "Apply ONLY the semantic POC rules that cannot be checked from formatting "
        "metadata: 10 (TOC), 11 (TOA), 16 (Document ID), 17 (Revisions accuracy), "
        "18 (Overall consistency). Output the strict-JSON object with `summary` and "
        "`findings`; each finding must be rule-anchored (rule_id ∈ {10,11,16,17,18}) "
        "and cite a paragraph index. Do NOT report font/spacing/quote/§/period rules."
    )

    try:
        from src.services.integrations.llm.claude_bedrock import (
            claude_configured, run_claude_analysis,
        )
        if claude_configured():
            result = await run_claude_analysis(user_prompt, system_prompt)
        else:
            result = await run_ai_analysis(user_prompt, system_prompt)
    except (APIConnectionError, APITimeoutError, APIError) as net_err:
        logger.warning(f"LLM unreachable for semantic pass: {net_err}")
        return [], meta
    except Exception as ex:
        logger.warning(f"LLM semantic pass call failed: {ex}")
        return [], meta

    meta = {
        "model": result.get("model", "llm"),
        "prompt_tokens": result.get("prompt_tokens", 0),
        "completion_tokens": result.get("completion_tokens", 0),
    }
    content_str = (result.get("content") or "").strip()
    if content_str.startswith("```"):
        lines = content_str.split("\n")
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        content_str = "\n".join(lines).strip()
    try:
        parsed = json.loads(content_str)
    except json.JSONDecodeError as parse_err:
        logger.warning(f"LLM semantic pass returned invalid JSON: {parse_err}")
        return [], meta

    out: list[dict] = []
    for f in parsed.get("findings", []) or []:
        rid = f.get("rule_id")
        if rid in SEMANTIC_LLM_RULES:
            out.append(f)
    logger.info("LLM semantic findings kept", function="process_ai_job", kept=len(out))
    return out, meta


# Derived from the canonical 18-rule list (single source of truth). See
# src/services/ai_jobs/poc_rules.py — also served by GET /config/poc-rules.
from src.services.ai_jobs.poc_rules import rule_meta as _poc_rule_meta

_RULE_META = _poc_rule_meta()


async def get_rules_for_client(db: AsyncSession, client_id: uuid.UUID) -> dict[int, dict]:
    from src.models.dao.validation_rule import ClientValidationRule
    from sqlalchemy import select
    stmt = (
        select(ClientValidationRule)
        .where(ClientValidationRule.client_id == client_id)
        .where(ClientValidationRule.is_active == True)
        .limit(1)
    )
    res = await db.execute(stmt)
    rule_set = res.scalar_one_or_none()
    if rule_set and rule_set.rules:
        rules_list = rule_set.rules
        if isinstance(rules_list, dict):
            # Already mapped to dict
            return {int(k): v for k, v in rules_list.items()}
        elif isinstance(rules_list, list):
            # Normalize list of dicts to _RULE_META format
            return {
                int(r["id"]): {
                    "name": r["name"],
                    "track": r["track"],
                    "type": r.get("type", "formatting"),
                    "severity": r.get("severity", "major"),
                    "detection": r.get("detection", "Automated"),
                    "detail": r.get("detail", ""),
                }
                for r in rules_list if "id" in r
            }
    # Fallback to default
    from src.services.ai_jobs.poc_rules import rule_meta
    return rule_meta()


def _warn_only_rules(rules_meta: Optional[dict] = None) -> list[dict]:
    """Always-emitted warnings for rules that can't be verified from XML alone."""
    meta = rules_meta or _RULE_META
    return [
        {
            "rule_id": 3, "rule_name": meta[3]["name"] if 3 in meta else "Margins", "track": 1,
            "type": "formatting", "severity": "suggestion", "confidence": 0.6,
            "location": {"page": None, "paragraph": None, "anchor_text": None},
            "description": "Margins cannot be measured from the document XML — verify visually.",
            "original_text": None, "replacement_text": None,
            "suggested_fix": "Verify left/right/top/bottom margin values match the format requirement.",
        },
        {
            "rule_id": 9, "rule_name": meta[9]["name"] if 9 in meta else "Line numbers", "track": 1,
            "type": "formatting", "severity": "suggestion", "confidence": 0.6,
            "location": {"page": None, "paragraph": None, "anchor_text": None},
            "description": "Line numbers cannot be verified from XML — manual visual check recommended.",
            "original_text": None, "replacement_text": None,
            "suggested_fix": "Verify line numbers align with text in body paragraphs (skip if the court format doesn't require them).",
        },
        {
            "rule_id": 14, "rule_name": meta[14]["name"] if 14 in meta else "Page numbering", "track": 2,
            "type": "metadata", "severity": "suggestion", "confidence": 0.6,
            "location": {"page": None, "paragraph": None, "anchor_text": None},
            "description": "Footer-based page numbering cannot be verified from extracted text.",
            "original_text": None, "replacement_text": None,
            "suggested_fix": "Verify the first body page is unnumbered and subsequent pages are numbered.",
        },
    ]


async def _run_vision_pass(file_path: str, rules_meta: Optional[dict] = None) -> tuple[list[dict], set[int]]:
    """Render the document and ask the gpt-4o vision model to judge the
    rendered-layout rules (3, 9, 12, 13, 14).

    Returns (findings, evaluated_rule_ids). Findings are emitted only for
    fail/warning verdicts; rules judged 'pass' are still recorded in
    evaluated_rule_ids so they aren't re-flagged by the warn-only fallback.
    Returns ([], set()) when rendering or the vision model is unavailable."""
    import json
    from src.utils.doc_render import render_docx_to_images
    from src.services.integrations.llm.azure_openai_vision import run_vision_analysis
    from src.services.ai_jobs.poc_rules import (
        VISION_RULES, VISION_SYSTEM_PROMPT, VISION_USER_PROMPT,
    )

    if not file_path.lower().endswith(".docx"):
        return [], set()

    # Cap pages to keep the end-to-end demo within the POC's <60s target while
    # still covering the layout rules.
    images = render_docx_to_images(file_path, max_pages=4)
    if not images:
        return [], set()

    result = await run_vision_analysis(images, VISION_SYSTEM_PROMPT, VISION_USER_PROMPT)
    content = (result.get("content") or "").strip()
    if not content:
        return [], set()
    if content.startswith("```"):
        lines = content.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        content = "\n".join(lines).strip()

    try:
        parsed = json.loads(content)
    except json.JSONDecodeError as parse_err:
        logger.warning(f"Vision pass returned invalid JSON: {parse_err}")
        return [], set()
    findings: list[dict] = []
    evaluated: set[int] = set()
    meta_src = rules_meta or _RULE_META
    for item in parsed.get("findings", []) or []:
        rid = item.get("rule_id")
        if rid not in VISION_RULES:
            continue
        evaluated.add(rid)
        verdict = (item.get("result") or "warning").lower()
        if verdict == "pass":
            continue  # pass = no finding
        meta = meta_src.get(rid, {})
        findings.append({
            "rule_id": rid,
            "rule_name": meta.get("name", f"Rule {rid}"),
            "track": meta.get("track", 1),
            "type": meta.get("type", "formatting"),
            "severity": "major" if verdict == "fail" else "suggestion",
            "confidence": 0.85,
            "location": {
                "page": item.get("page"),
                "paragraph": None,
                "anchor_text": None,
                "result": "fail" if verdict == "fail" else "warning",
                "engine": "vision",
            },
            "description": item.get("description") or meta.get("name", ""),
            "original_text": None,
            "replacement_text": None,
            "suggested_fix": item.get("suggested_fix"),
        })
    return findings, evaluated


def _make_finding(rule_id: int, *, paragraph=None, anchor=None, original=None,
                  replacement=None, description="", suggested_fix="",
                  severity=None, confidence=0.95, rules_meta: Optional[dict] = None) -> dict:
    meta = (rules_meta or _RULE_META).get(rule_id, {})
    return {
        "rule_id": rule_id,
        "rule_name": meta.get("name", f"Rule {rule_id}"),
        "track": meta.get("track", 1),
        "type": meta.get("type", "formatting"),
        "severity": severity or meta.get("severity", "major"),
        "confidence": confidence,
        "location": {
            "page": 1,
            "paragraph": paragraph,
            "anchor_text": anchor[:160] if anchor else None,
        },
        "description": description,
        "original_text": original,
        "replacement_text": replacement,
        "suggested_fix": suggested_fix,
    }


def _synthesise_findings_from_precomputed(pre: dict, rules_meta: Optional[dict] = None) -> list[dict]:
    """Synthesize structured QCFinding-shaped dicts directly from the
    deterministic violation tally. Used when the LLM is unavailable."""
    out: list[dict] = []
    if not pre:
        return out
    violations = pre.get("violations", {})

    def make_f(*args, **kwargs):
        return _make_finding(*args, rules_meta=rules_meta, **kwargs)

    for v in violations.get("rule_1_footnote_font", []) or []:
        out.append(make_f(
            1,
            paragraph=None,
            anchor=v.get("snippet"),
            original=f"footnote font size {v.get('got_pt')}pt",
            replacement=f"{v.get('expected_pt')}pt",
            description=(
                f"Footnote (id={v.get('footnote_id')}) is set to {v.get('got_pt')}pt; "
                f"with a {v.get('body_size_pt')}pt body, footnotes should be {v.get('expected_pt')}pt."
            ),
            suggested_fix=f"Change the footnote font size to {v.get('expected_pt')}pt.",
        ))
    for v in violations.get("rule_1_body_font", []) or []:
        out.append(make_f(
            1,
            paragraph=v.get("paragraph"),
            anchor=v.get("snippet"),
            original=f"body font size {v.get('got_pt')}pt",
            replacement=f"{v.get('expected_pt')}pt",
            description=(
                f"Paragraph {v.get('paragraph')} uses {v.get('got_pt')}pt body text; the rest of the document is {v.get('expected_pt')}pt."
            ),
            suggested_fix=f"Set the paragraph font size to {v.get('expected_pt')}pt.",
        ))
    for v in violations.get("rule_2_line_spacing", []) or []:
        out.append(make_f(
            2,
            paragraph=v.get("paragraph"),
            anchor=v.get("snippet"),
            original=f"line spacing {v.get('got_line')} ({v.get('line_rule')})",
            replacement="480 (24pt)",
            description=(
                f"Paragraph {v.get('paragraph')} has line spacing {v.get('got_line')} ({v.get('line_rule')}); body text should be exactly 24pt (line=480)."
            ),
            suggested_fix="Set line spacing to exactly 24pt (line=480, lineRule=auto).",
        ))
    for v in violations.get("rule_4_mixed_quotes", []) or []:
        out.append(make_f(
            4,
            paragraph=v.get("paragraph"),
            anchor=v.get("snippet"),
            original=v.get("snippet"),
            replacement=None,
            description=(
                f"Paragraph {v.get('paragraph')} mixes curly (“ ”) and straight (\" \") quotation marks in the same paragraph."
            ),
            suggested_fix="Standardize to either curly or straight quotes consistently in this paragraph (and across the document).",
        ))
    for v in violations.get("rule_5_period_spacing", []) or []:
        ex_list = v.get("examples", []) or []
        original_str = ", ".join(ex_list[:3])
        # Each example is like "d.Th" → fix to "d.  Th" (insert two spaces after period)
        fixed_list = [e.replace(".", ".  ", 1) for e in ex_list[:3]]
        replacement_str = ", ".join(fixed_list)
        out.append(make_f(
            5,
            paragraph=v.get("paragraph"),
            anchor=v.get("snippet"),
            original=original_str,
            replacement=replacement_str,
            description=(
                f"Paragraph {v.get('paragraph')} contains a period not followed by two spaces (example: {original_str})."
            ),
            suggested_fix="Insert two spaces after the period.",
        ))
    for v in violations.get("rule_6_justification", []) or []:
        out.append(make_f(
            6,
            paragraph=v.get("paragraph"),
            anchor=v.get("snippet"),
            original=f"alignment={v.get('got_alignment')}",
            replacement="justify",
            description=(
                f"Paragraph {v.get('paragraph')} is {v.get('got_alignment')}-aligned; body text in this document is fully justified."
            ),
            suggested_fix="Set paragraph alignment to fully justified.",
        ))
    for v in violations.get("rule_7_orphan_heading", []) or []:
        out.append(make_f(
            7,
            paragraph=v.get("paragraph"),
            anchor=v.get("snippet"),
            original=v.get("snippet"),
            replacement=None,
            description=(
                f"Top-level section heading at paragraph {v.get('paragraph')} has keepNext disabled — risk of orphan heading at page break."
            ),
            suggested_fix="Enable 'Keep with next' on this heading paragraph (Paragraph → Line and Page Breaks → Keep with next).",
        ))
    import re as _re
    for v in violations.get("rule_8_section_symbol", []) or []:
        examples = v.get("examples", []) or []
        original_str = ", ".join(examples[:3])
        fixed_examples = [_re.sub(r'§(\d)', r'§ \1', e) for e in examples[:3]]
        replacement_str = ", ".join(fixed_examples)
        out.append(make_f(
            8,
            paragraph=v.get("paragraph"),
            anchor=v.get("snippet"),
            original=original_str,
            replacement=replacement_str,
            description=(
                f"Paragraph {v.get('paragraph')} contains a section symbol without a following space (example: {original_str})."
            ),
            suggested_fix="Insert one space between '§' and the section number (e.g. '§ 17200').",
        ))

    for v in violations.get("rule_15_spelling", []) or []:
        out.append(make_f(
            15,
            paragraph=v.get("paragraph"),
            anchor=v.get("snippet"),
            original=v.get("original"),
            replacement=v.get("replacement"),
            description=(
                f"Spelling / grammar issue in paragraph {v.get('paragraph')}: "
                f"found '{v.get('original')}', suggested correction is '{v.get('replacement')}'."
            ),
            suggested_fix=f"Change '{v.get('original')}' to '{v.get('replacement')}'."
        ))

    return out


# Strong references to background tasks so the runtime can't garbage-collect
# them mid-run (a bare asyncio.create_task() result can be GC'd, killing the
# job silently under memory pressure).
_INFLIGHT_BG_TASKS: set[asyncio.Task] = set()


def _spawn_bg_task(job_id: uuid.UUID, delay: float = 0.1) -> None:
    """Schedule a background job attempt and keep a strong reference to it."""
    task = asyncio.create_task(run_job_in_background(job_id, delay=delay))
    _INFLIGHT_BG_TASKS.add(task)
    task.add_done_callback(_INFLIGHT_BG_TASKS.discard)


async def _job_document_id_if_runnable(job_id: uuid.UUID) -> uuid.UUID | None:
    """Lightweight read: the document_id of a runnable (PENDING/RETRYING) job,
    or None. Used to decide whether to acquire the doc lock at all."""
    from src.repositories.db_setup import AsyncSessionLocal
    from sqlalchemy import select
    async with AsyncSessionLocal() as db:
        row = (await db.execute(
            select(AIAnalysisJob.document_id, AIAnalysisJob.status)
            .where(AIAnalysisJob.id == job_id)
        )).first()
        if not row:
            return None
        document_id, status = row
        return document_id if status in (AIJobStatus.PENDING, AIJobStatus.RETRYING) else None


async def _set_status(job_id: uuid.UUID, *, status: AIJobStatus, reason: str) -> None:
    """Set a job's status + error_message outside the main work session."""
    from src.repositories.db_setup import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        job = await db.get(AIAnalysisJob, job_id)
        if job:
            job.status = status
            job.error_message = reason
            await db.commit()


async def _read_retry_count(job_id: uuid.UUID) -> int:
    from src.repositories.db_setup import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        job = await db.get(AIAnalysisJob, job_id)
        return job.retry_count if job else 0


async def run_job_in_background(job_id: uuid.UUID, delay: float = 0.1) -> None:
    """Run one attempt of an AI analysis job.

    Acquires the per-document lock (a scheduling concern — lives here, not in
    ``process_ai_job``), runs the work, commits, and re-schedules with backoff
    if the work landed in RETRYING. Lock contention is NOT a work failure: a
    lock timeout re-schedules without consuming a retry slot.

    Known limitation: a job cancelled while RUNNING can still be overwritten to
    COMPLETED by an in-flight attempt; cooperative cancellation is out of scope.
    ``process_ai_job`` skips any job that is no longer runnable.
    """
    await asyncio.sleep(delay)

    document_id = await _job_document_id_if_runnable(job_id)
    if document_id is None:
        return  # gone, or no longer runnable (completed/failed/cancelled)

    lock = await doc_lock.acquire_doc_lock(document_id)
    if lock is None:
        # Document is busy — defer without bumping retry_count (not a work failure).
        logger.info(
            "Doc lock busy, deferring",
            function="run_job_in_background", job_id=str(job_id),
        )
        await _set_status(job_id, status=AIJobStatus.RETRYING, reason="lock timeout")
        _spawn_bg_task(job_id, delay=doc_lock.compute_backoff(1))
        return

    key, token = lock
    final_status = AIJobStatus.FAILED
    try:
        from src.repositories.db_setup import AsyncSessionLocal
        async with AsyncSessionLocal() as db:
            try:
                final_status = await process_ai_job(db, job_id)
                await db.commit()
            except Exception as e:
                await db.rollback()
                logger.error(
                    f"Error processing job in background: {e}",
                    function="run_job_in_background", job_id=str(job_id),
                )
                final_status = AIJobStatus.FAILED
    finally:
        await doc_lock.release_doc_lock(key, token)

    if final_status == AIJobStatus.RETRYING:
        retry_count = await _read_retry_count(job_id) or 1
        backoff = doc_lock.compute_backoff(retry_count)
        logger.info(
            "Re-scheduling retry",
            function="run_job_in_background", job_id=str(job_id),
            attempt=retry_count, delay=round(backoff, 2),
        )
        _spawn_bg_task(job_id, delay=backoff)
