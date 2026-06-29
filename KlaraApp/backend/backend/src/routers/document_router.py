from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Header, Request, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.repositories.db_setup import get_db
from src.utils.dependencies import get_current_user, require_roles
from src.models.dto.schemas.auth import UserClaims
from src.models.enum.user_role import UserRole
from src.models.enum.document_status import DocumentStatus
from src.models.enum.document_type import DocumentType
from src.models.dao.document import Document
from src.models.dao.user import User
from src.services.documents import document_service, document_comparison_service
from src.repositories import document_repo
from src.models.dto.schemas.documents import (
    CreateDocumentRequest,
    CreateDocumentResponse,
    DocumentResponse,
    DocumentListResponse,
    UpdateDocumentStatusRequest,
    AssignDocumentRequest,
    DocumentVersionResponse,
)
from src.core.logger import get_logger_with_context

logger = get_logger_with_context()
router = APIRouter()

# Last OnlyOffice editor key handed out per document. The editor keeps this key
# for the life of an editing session even after intermediate saves change the
# file mtime, so we remember it to issue a forcesave against the right session.
_editor_keys: dict[str, str] = {}


def _internalize_onlyoffice_url(url: str) -> str:
    """Rewrite an OnlyOffice browser-facing URL (e.g. http://localhost:8080/...)
    to the address the backend container can actually reach (the internal docker
    service ``onlyoffice`` on port 80)."""
    try:
        from urllib.parse import urlparse, urlunparse
        p = urlparse(url)
        if p.hostname in ("localhost", "127.0.0.1") or p.port == 8080:
            return urlunparse(p._replace(netloc="onlyoffice"))
    except Exception:
        pass
    return url


async def _onlyoffice_forcesave(
    document_id: UUID, file_path: str, session_key: str | None = None
) -> dict:
    """Ask the OnlyOffice command service to flush the live editing session for
    this document to disk (it triggers our callback with the edited content).
    Returns {error, key, changed} where ``changed`` is True once the file on disk
    actually updates. Best-effort and safe when no session is open.

    ``session_key`` (persisted at editor-config time) is the most reliable key —
    it matches the live editor even after intermediate saves changed the file
    mtime. We fall back to the in-memory registry, then a recomputed key."""
    import asyncio
    import os
    import httpx

    key = session_key or _editor_keys.get(str(document_id))
    if not key and file_path and os.path.exists(file_path):
        mtime = int(os.path.getmtime(file_path))
        key = f"{str(document_id).replace('-', '')}_{mtime}"
    if not key:
        return {"error": -1, "key": None, "changed": False}

    before = os.path.getmtime(file_path) if file_path and os.path.exists(file_path) else None
    err = None
    payload = {"c": "forcesave", "key": key}
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                "http://onlyoffice/coauthoring/CommandService.ashx", json=payload
            )
            data = resp.json()
            err = data.get("error") if isinstance(data, dict) else None
            logger.info("OnlyOffice forcesave issued", key=key, response=data)
    except Exception as ex:
        logger.warning(f"OnlyOffice forcesave call failed: {ex}")
        return {"error": -2, "key": key, "changed": False}

    # error 0 → forcesave performed; wait for the callback to write the file.
    changed = False
    if err == 0 and before is not None:
        for _ in range(24):  # up to ~12s
            await asyncio.sleep(0.5)
            try:
                if os.path.getmtime(file_path) != before:
                    changed = True
                    break
            except OSError:
                pass
    return {"error": err, "key": key, "changed": changed}


@router.get("", response_model=DocumentListResponse)
async def list_documents(
    client_id: Optional[UUID] = Query(None),
    status: Optional[DocumentStatus] = Query(None),
    document_type: Optional[DocumentType] = Query(None),
    cursor: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    current_user: UserClaims = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List documents. Role-scoped: specialists see only their assigned docs;
    QC operators see only docs in qc_review; coordinators/managers/admins see all."""
    logger.info("Entering list_documents", function="list_documents", action="entry",
                user_id=str(current_user.id), role=current_user.role)

    # Role-based scope enforcement — prevents 403s by simply filtering instead
    scoped_specialist_id: Optional[UUID] = None
    scoped_status: Optional[DocumentStatus] = status

    if current_user.role == UserRole.DOC_SPECIALIST:
        # Specialists only see documents assigned to them
        scoped_specialist_id = current_user.id
    elif current_user.role == UserRole.PROOFREADER:
        # Proofreaders only see documents assigned to them
        scoped_specialist_id = current_user.id
    elif current_user.role == UserRole.QC_OPERATOR:
        # QC operators only see documents in qc_review (or filter can override to narrower)
        if scoped_status is None:
            scoped_status = DocumentStatus.QC_REVIEW

    result = await document_service.list_documents(
        db,
        client_id=client_id,
        status=scoped_status,
        document_type=document_type,
        cursor=cursor,
        limit=limit,
        assigned_specialist_id=scoped_specialist_id,
    )
    logger.info("Exiting list_documents", function="list_documents", action="exit",
                document_count=len(result.get("data", [])))
    return result


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: UUID,
    current_user: UserClaims = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get document details."""
    logger.info("Entering get_document", function="get_document", action="entry", document_id=str(document_id), user_id=current_user.id)
    doc = await document_service.get_document(db, document_id)
    logger.info("Exiting get_document", function="get_document", action="exit", document_id=str(document_id))
    return DocumentResponse.model_validate(doc)


@router.post("", response_model=CreateDocumentResponse, status_code=202)
async def create_document(
    body: CreateDocumentRequest,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    current_user: UserClaims = Depends(
        require_roles([
            UserRole.INTAKE_COORDINATOR, UserRole.DOC_SPECIALIST,
            UserRole.QC_OPERATOR, UserRole.PROOFREADER,
            UserRole.MANAGER, UserRole.ADMIN,
        ])
    ),
    db: AsyncSession = Depends(get_db),
):
    """Submit a new document for processing."""
    logger.info("Entering create_document", function="create_document", action="entry", user_id=current_user.id, idempotency_key=idempotency_key, client_id=str(body.client_id))
    result = await document_service.create_document(db, body, actor_id=current_user.id)
    logger.info("Exiting create_document", function="create_document", action="exit", document_id=str(result.id))
    return result


@router.patch("/{document_id}/status", response_model=DocumentResponse)
async def update_status(
    document_id: UUID,
    body: UpdateDocumentStatusRequest,
    current_user: UserClaims = Depends(
        require_roles([
            UserRole.INTAKE_COORDINATOR,
            UserRole.DOC_SPECIALIST,
            UserRole.QC_OPERATOR,
            UserRole.PROOFREADER,
            UserRole.MANAGER,
            UserRole.ADMIN,
        ])
    ),
    db: AsyncSession = Depends(get_db),
):
    """Update document processing status."""
    logger.info("Entering update_status", function="update_status", action="entry", document_id=str(document_id), new_status=body.status, user_id=current_user.id)
    result = await document_service.update_document_status(db, document_id, body, actor_id=current_user.id)
    logger.info("Exiting update_status", function="update_status", action="exit", document_id=str(document_id))
    return result


@router.patch("/{document_id}/assign", response_model=DocumentResponse)
async def assign_document(
    document_id: UUID,
    body: AssignDocumentRequest,
    current_user: UserClaims = Depends(
        require_roles([UserRole.INTAKE_COORDINATOR, UserRole.MANAGER, UserRole.ADMIN])
    ),
    db: AsyncSession = Depends(get_db),
):
    """Assign document to a specialist or proofreader."""
    logger.info("Entering assign_document", function="assign_document", action="entry", document_id=str(document_id), specialist_id=str(body.specialist_id), user_id=current_user.id)
    result = await document_service.assign_document(db, document_id, body, actor_id=current_user.id)
    logger.info("Exiting assign_document", function="assign_document", action="exit", document_id=str(document_id))
    return result


@router.get("/{document_id}/versions", response_model=list[DocumentVersionResponse])
async def get_versions(
    document_id: UUID,
    current_user: UserClaims = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List document version history."""
    logger.info("Entering get_versions", function="get_versions", action="entry", document_id=str(document_id), user_id=current_user.id)
    result = await document_service.get_document_versions(db, document_id)
    logger.info("Exiting get_versions", function="get_versions", action="exit", document_id=str(document_id), version_count=len(result))
    return result


@router.get("/{document_id}/content")
async def get_document_content(
    document_id: UUID,
    current_user: UserClaims = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return an HTML preview + plain text of the saved document.

    Used by the workspace and QC viewer to show the source document
    inline (side-by-side with AI suggestions) without forcing the user
    to download the file. Best-effort: returns empty content if no file
    can be located on disk."""
    import os
    from src.utils.text_extractor import docx_to_html, extract_text_from_file

    doc = await document_service.get_document(db, document_id)
    file_path = document_comparison_service.resolve_document_file(doc)
    if not file_path:
        return {"data": {"html": "", "text": "", "source": "missing", "filename": doc.title}}

    ext = os.path.splitext(file_path)[1].lower()
    html_str = docx_to_html(file_path) if ext == ".docx" else ""
    text_str = extract_text_from_file(file_path)
    return {
        "data": {
            "html": html_str,
            "text": text_str,
            "source": "file",
            "filename": os.path.basename(file_path),
        }
    }


@router.get("/{document_id}/comparison")
async def get_document_comparison(
    document_id: UUID,
    current_user: UserClaims = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return a before/after comparison of the document.

    ``before_html`` is the pristine original; ``after_html`` and ``redline_html``
    are a real redline of the *current* document against it — the reviewer's
    manual edits plus the AI changes they accepted (pending AI suggestions are
    excluded). Deletions render red/struck, insertions green. ``rule_findings``
    and ``summary`` still drive the per-rule details tab."""
    import os

    doc = await document_service.get_document(db, document_id)
    corrections = await document_comparison_service.collect_corrections(db, document_id)
    applied_keys = {(c["original"], c["replacement"]) for c in corrections}
    rule_findings = await document_comparison_service.collect_rule_findings(
        db, document_id, applied_keys
    )
    summary = document_comparison_service.result_summary(rule_findings)

    current_path = document_comparison_service.resolve_document_file(doc)
    original_path = document_comparison_service.resolve_original_file(doc)
    if not current_path:
        return {
            "data": {
                "before_html": "", "after_html": "", "redline_html": "",
                "changes": corrections, "rule_findings": rule_findings,
                "summary": summary,
                "changes_index": [], "changed_pages": [], "pages_total": 1,
                "change_stats": {"insertions": 0, "deletions": 0,
                                 "paragraphs_changed": 0, "has_changes": False,
                                 "pages_total": 1, "changed_pages": []},
                "filename": doc.title, "source": "missing",
            }
        }
    # "Compare original vs AI": diff the pristine original against the
    # AI-corrected document (original + the engine's findings applied), not the
    # raw working file — the AI's corrections live in findings, never on disk.
    corrected_path = document_comparison_service.build_ai_corrected_file(
        str(document_id), original_path, corrections
    )
    comp = document_comparison_service.build_change_diff(original_path, corrected_path)
    comp["changes"] = corrections
    comp["rule_findings"] = rule_findings
    comp["summary"] = summary
    comp["filename"] = os.path.basename(current_path)
    comp["source"] = "file"
    return {"data": comp}


@router.get("/{document_id}/comparison/pages")
async def get_comparison_pages(
    document_id: UUID,
    current_user: UserClaims = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Render the original and a highlighted redline to page images and report,
    per page, whether it carries a change. Drives the image-based "Compare
    original vs AI" view. First call renders (a few seconds); cached thereafter."""
    doc = await document_service.get_document(db, document_id)
    original_path = document_comparison_service.resolve_original_file(doc)
    # Render the pristine original vs the AI-corrected document (original + the
    # engine's findings applied), so highlighted pages reflect the AI's changes.
    corrections = await document_comparison_service.collect_corrections(db, document_id)
    corrected_path = document_comparison_service.build_ai_corrected_file(
        str(document_id), original_path, corrections
    )
    data = document_comparison_service.build_comparison_images(
        str(document_id), original_path, corrected_path
    )
    return {"data": data}


@router.get("/{document_id}/comparison/page/{page}")
async def get_comparison_page_image(
    document_id: UUID,
    page: int,
    side: str = Query("redline", pattern="^(redline|original)$"),
    current_user: UserClaims = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Serve a single rendered comparison page as a PNG (redline or original)."""
    doc = await document_service.get_document(db, document_id)
    original_path = document_comparison_service.resolve_original_file(doc)
    # Mirror /comparison/pages: serve from the original-vs-AI-corrected render.
    corrections = await document_comparison_service.collect_corrections(db, document_id)
    corrected_path = document_comparison_service.build_ai_corrected_file(
        str(document_id), original_path, corrections
    )
    fp = document_comparison_service.comparison_page_file(
        str(document_id), original_path, corrected_path, page, side
    )
    if not fp:
        raise HTTPException(status_code=404, detail="Comparison page not available")
    with open(fp, "rb") as f:
        data = f.read()
    return Response(content=data, media_type="image/png",
                    headers={"Cache-Control": "private, max-age=300"})


@router.get("/{document_id}/download")
async def download_document(
    document_id: UUID,
    version: str = Query("original", pattern="^(original|processed)$"),
    current_user: UserClaims = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Download the document. version=original streams the provided file;
    version=processed generates a corrected .docx with the QC-accepted
    corrections applied."""
    import os

    doc = await document_service.get_document(db, document_id)
    file_path = document_comparison_service.resolve_document_file(doc)
    if not file_path or not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Source document file not found")

    base = os.path.basename(file_path)
    name, ext = os.path.splitext(base)

    if version == "processed":
        corrections = await document_comparison_service.collect_corrections(db, document_id)
        data = document_comparison_service.generate_processed_docx(file_path, corrections)
        filename = f"{name}-processed.docx"
        media_type = document_comparison_service.WORD_MEDIA_TYPE
    else:
        with open(file_path, "rb") as f:
            data = f.read()
        filename = base
        media_type = (
            document_comparison_service.WORD_MEDIA_TYPE if ext.lower() == ".docx"
            else "application/octet-stream"
        )

    return Response(
        content=data,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


class UpdateValidationModeRequest(BaseModel):
    validation_mode: str  # "auto" | "review_assist"


@router.patch("/{document_id}/validation-mode", response_model=DocumentResponse)
async def update_validation_mode(
    document_id: UUID,
    request: Request,
    current_user: UserClaims = Depends(
        require_roles([
            UserRole.INTAKE_COORDINATOR, UserRole.DOC_SPECIALIST,
            UserRole.QC_OPERATOR, UserRole.PROOFREADER,
            UserRole.MANAGER, UserRole.ADMIN,
        ])
    ),
    db: AsyncSession = Depends(get_db),
):
    """Switch between 'auto' (first-pass QA on upload) and 'review_assist' (on-demand) mode."""
    body = await request.json()
    mode = body.get("validation_mode", "auto")
    if mode not in ("auto", "review_assist"):
        raise HTTPException(status_code=422, detail="validation_mode must be 'auto' or 'review_assist'")

    from src.services.documents import document_service as doc_svc
    doc = await doc_svc.get_document(db, document_id)
    doc.validation_mode = mode
    await db.flush()
    return DocumentResponse.model_validate(doc)


@router.post("/{document_id}/run-klara", response_model=dict, status_code=202)
async def run_klara_on_demand(
    document_id: UUID,
    current_user: UserClaims = Depends(
        require_roles([
            UserRole.INTAKE_COORDINATOR, UserRole.DOC_SPECIALIST,
            UserRole.QC_OPERATOR, UserRole.PROOFREADER,
            UserRole.MANAGER, UserRole.ADMIN,
        ])
    ),
    db: AsyncSession = Depends(get_db),
):
    """Trigger an on-demand Klara QA run (used when validation_mode is 'review_assist')."""
    from src.services.documents import document_service as doc_svc
    from src.services.ai_jobs.ai_job_service import create_ai_job
    from src.models.dto.schemas.ai_jobs import CreateAIJobRequest
    from src.models.enum.job_type import AIJobType
    from src.models.enum.document_type import DocumentType

    doc = await doc_svc.get_document(db, document_id)
    job_type = (
        AIJobType.PROOFREADING
        if doc.document_type == DocumentType.PROOFREADING
        else AIJobType.FORMATTING_CHECK
    )
    logger.info("Triggering on-demand Klara run", document_id=str(document_id), job_type=job_type.value)
    result = await create_ai_job(
        db=db,
        body=CreateAIJobRequest(document_id=document_id, job_type=job_type),
        actor_id=current_user.id,
    )
    return {"job_id": str(result.id), "status": result.status, "message": "Klara analysis started"}


@router.put("/upload-local")
async def upload_local(
    request: Request,
    container: str = Query(...),
    blob_path: str = Query(...),
    document_id: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """Receive raw binary data from local/mock upload and save it locally.
    Also updates the document blob_url to a browser-accessible /uploads/{filename} path.
    """
    import os
    logger.info("Entering upload_local", function="upload_local", container=container, blob_path=blob_path, document_id=document_id)
    body = await request.body()
    filename = os.path.basename(blob_path)
    # Prefer the container-mounted /uploads path (which is the host's
    # frontend/uploads). Fall back to project-root path for host runs.
    if os.path.isdir("/uploads"):
        upload_dir = "/uploads"
    else:
        router_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(router_dir)))
        upload_dir = os.path.join(project_root, "frontend", "uploads")
        os.makedirs(upload_dir, exist_ok=True)
    file_path = os.path.join(upload_dir, filename)
    with open(file_path, "wb") as f:
        f.write(body)

    # Accept any pending tracked changes the uploaded document still carries
    # (a reviewing attorney's edits, prior AI suggestions, …) so the QA engine
    # and the editor start from a single clean baseline. No-op for clean docs.
    from src.utils.docx_revisions import accept_all_revisions
    try:
        accept_summary = accept_all_revisions(file_path)
        if accept_summary.get("changed"):
            logger.info(
                "Flattened pending changes on upload",
                function="upload_local", document_id=document_id, **accept_summary,
            )
    except Exception as ex:
        logger.error(f"Failed to accept pending changes on upload: {ex}", function="upload_local")

    # A fresh upload resets the comparison baseline: snapshot the (now
    # changes-accepted) file as the pristine original so later edits can be
    # diffed against it.
    document_comparison_service.ensure_original_backup(file_path, refresh=True)

    # Construct a URL the browser can load via the Vite dev-server static plugin
    local_url = f"/uploads/{filename}"

    # Update the document record so blob_url points to the real file
    if document_id:
        try:
            from uuid import UUID
            doc_uuid = UUID(document_id)
            doc = await document_repo.find_by_id(db, doc_uuid)
            if doc:
                doc.blob_url = local_url
                await db.flush()
                logger.info("Updated document blob_url", function="upload_local", document_id=document_id, local_url=local_url)
                # Now that the real file has landed, kick off the automatic
                # first-pass Klara run (no-op unless the client/document is in
                # 'auto' validation mode). Runs against the actual upload — not a
                # canned fallback — which is why it lives here, not at create time.
                await document_service.trigger_auto_klara(db, doc, actor_id=doc.assigned_specialist_id)
        except Exception as ex:
            logger.error(f"Failed to update blob_url for document {document_id}: {ex}", function="upload_local")

    logger.info("Exiting upload_local", function="upload_local", file_path=file_path)
    return {"status": "success", "file_path": file_path, "local_url": local_url}


@router.get("/onlyoffice/health")
async def onlyoffice_health():
    """Proxy OnlyOffice healthcheck so the frontend can check readiness."""
    import httpx
    try:
        async with httpx.AsyncClient(timeout=3) as client:
            for url in ["http://onlyoffice:80/healthcheck", "http://localhost:8080/healthcheck"]:
                try:
                    r = await client.get(url)
                    if r.text.strip() == "true":
                        return {"ready": True}
                except Exception:
                    continue
        return {"ready": False}
    except Exception:
        return {"ready": False}


@router.get("/{document_id}/onlyoffice/config")
async def onlyoffice_config(
    document_id: UUID,
    v: Optional[str] = Query(None),
    current_user: UserClaims = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return OnlyOffice editor config for the frontend."""
    import os
    doc = await document_service.get_document(db, document_id)
    file_path = document_comparison_service.resolve_document_file(doc)
    if not file_path:
        raise HTTPException(status_code=404, detail="Source document file not found")
    
    # Generate key based on document_id and mtime
    mtime = int(os.path.getmtime(file_path))
    key = f"{str(document_id).replace('-', '')}_{mtime}"
    if v:
        key = f"{key}_{v}"
    # Remember this session key so we can forcesave it on demand later. Persist
    # to the document row too, so it survives a backend reload mid-session.
    _editor_keys[str(document_id)] = key
    try:
        md = dict(doc.metadata_ or {})
        md["oo_key"] = key
        doc.metadata_ = md
        await db.flush()
        await db.commit()
    except Exception as e:
        logger.warning(f"Could not persist OnlyOffice key: {e}")

    config = {
        "document": {
            "fileType": "docx",
            "key": key,
            "title": doc.title or "document.docx",
            "url": f"http://backend:8000/api/v1/documents/{document_id}/onlyoffice/file",
            # OnlyOffice reads `permissions` from `document`, NOT `editorConfig`.
            # Nested under editorConfig it is silently ignored, so review rights
            # fall back to the default and the native "Review changes" navigator
            # (prev/next arrows + Accept/Reject) is disabled even when the doc
            # carries tracked changes.
            "permissions": {
                "edit": True,
                "review": True,
                "comment": True,
            },
        },
        "documentType": "word",
        "editorConfig": {
            "mode": "edit",
            "callbackUrl": f"http://backend:8000/api/v1/documents/{document_id}/onlyoffice/callback",
            "user": {
                "id": str(current_user.id),
                "name": current_user.display_name or "User",
            },
            "customization": {
                "autosave": True,
                "forcesave": True,
                "chat": False,
                "comments": True,
                "compactHeader": True,
                "review": {
                    "trackChanges": False,
                    # The native OnlyOffice floating navigator is hidden for everyone;
                    # Klara renders its own custom "Review changes" toolbar instead.
                    "showReviewChanges": False,
                    "reviewDisplay": "markup",
                },
            },
        },
    }
    return config


@router.get("/{document_id}/onlyoffice/file")
async def onlyoffice_file(
    document_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Serve docx file with native tracked changes (revisions) to OnlyOffice server."""
    import os
    doc = await document_service.get_document(db, document_id)
    file_path = document_comparison_service.resolve_document_file(doc)
    if not file_path or not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Source document file not found")
    
    # Generate revisioned document
    corrections = await document_comparison_service.collect_corrections(db, document_id)
    data = document_comparison_service.generate_revisioned_docx(file_path, corrections)
    
    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{doc.title or "document.docx"}"'}
    )


@router.post("/{document_id}/onlyoffice/callback")
async def onlyoffice_callback(
    document_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """OnlyOffice calls this when the user saves the document."""
    import httpx
    import os
    body = await request.json()
    status = body.get("status")
    logger.info("OnlyOffice callback received", document_id=str(document_id), status=status)
    
    if status in (2, 6):
        download_url = body.get("url")
        if download_url:
            # OnlyOffice builds this URL from its *browser-facing* address
            # (e.g. http://localhost:8080/cache/...), which is NOT reachable from
            # inside the backend container — the GET would fail and the edit would
            # never hit disk. Rewrite the host to the internal docker service.
            fetch_url = _internalize_onlyoffice_url(download_url)
            logger.info(f"Downloading edited document from OnlyOffice: {download_url} (fetching via {fetch_url})")
            try:
                async with httpx.AsyncClient(timeout=30) as client:
                    r = await client.get(fetch_url)
                    r.raise_for_status()
            except Exception as ex:
                logger.error(f"Failed to download edited document from OnlyOffice: {ex}")
                return {"error": 1}

            doc = await document_service.get_document(db, document_id)
            file_path = document_comparison_service.resolve_document_file(doc)
            if not file_path:
                if os.path.isdir("/uploads"):
                    file_path = os.path.join("/uploads", doc.title)
                else:
                    router_dir = os.path.dirname(os.path.abspath(__file__))
                    project_root = os.path.dirname(os.path.dirname(os.path.dirname(router_dir)))
                    file_path = os.path.join(project_root, "frontend", "uploads", doc.title)

            # Preserve the pre-edit state once, before we overwrite the working
            # file, so the change-comparison always has a pristine original to
            # diff against (no-op if a snapshot already exists).
            document_comparison_service.ensure_original_backup(file_path, refresh=False)

            with open(file_path, "wb") as f:
                f.write(r.content)
            logger.info("Saved edited document to disk", file_path=file_path, bytes=len(r.content))

            # NOTE: do NOT trigger a Klara re-analysis here. Saving the document
            # in the editor happens at every workflow stage (specialist, QC,
            # proofreader), so re-running AI on save makes the AI status flip to
            # "running" again at each stage hand-off — which is not desired. The
            # automatic Klara run fires exactly once, on the initial upload (see
            # `trigger_auto_klara` in the upload-local handler); in manual /
            # review_assist mode it only runs when the reviewer explicitly hits
            # the "Run Klara" button (the run-klara endpoint).
            logger.info("Saved edited document to disk. Not re-triggering AI (runs on upload / on-demand only).")

    return {"error": 0}


# Microsoft Graph and SharePoint Integration Endpoints

@router.get("/sharepoint/sites", response_model=dict)
async def get_sharepoint_sites(
    search: Optional[str] = Query(None),
    current_user: UserClaims = Depends(get_current_user),
):
    """Get SharePoint sites accessible to authenticated user."""
    logger.info("Entering get_sharepoint_sites", function="get_sharepoint_sites", search=search)

    try:
        from src.services.integrations.microsoft_graph.sharepoint_service import SharePointService

        # Get user's Microsoft access token (this would need to be stored/retrieved)
        # For now, return error if no token
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Microsoft Graph integration requires user authentication token"
        )

        # TODO: Implement token retrieval from user session or database
        # access_token = await get_user_microsoft_token(current_user.id)
        # sharepoint_service = SharePointService(access_token)
        # sites = await sharepoint_service.get_accessible_sites(search=search)
        # await sharepoint_service.close()
        # return {"data": sites}

    except HTTPException:
        raise
    except Exception as e:
        logger.error("get_sharepoint_sites_failed", function="get_sharepoint_sites", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get SharePoint sites: {str(e)}"
        )


@router.get("/sharepoint/sites/{site_id}/libraries", response_model=dict)
async def get_sharepoint_libraries(
    site_id: str,
    current_user: UserClaims = Depends(get_current_user),
):
    """Get document libraries for a SharePoint site."""
    logger.info("Entering get_sharepoint_libraries", function="get_sharepoint_libraries", site_id=site_id)

    try:
        from src.services.integrations.microsoft_graph.sharepoint_service import SharePointService

        # TODO: Implement token retrieval from user session or database
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Microsoft Graph integration requires user authentication token"
        )

        # access_token = await get_user_microsoft_token(current_user.id)
        # sharepoint_service = SharePointService(access_token)
        # libraries = await sharepoint_service.get_document_libraries(site_id)
        # await sharepoint_service.close()
        # return {"data": libraries}

    except HTTPException:
        raise
    except Exception as e:
        logger.error("get_sharepoint_libraries_failed", function="get_sharepoint_libraries", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get SharePoint libraries: {str(e)}"
        )


@router.get("/sharepoint/libraries/{drive_id}/documents", response_model=dict)
async def get_sharepoint_documents(
    drive_id: str,
    folder_path: Optional[str] = Query(None),
    current_user: UserClaims = Depends(get_current_user),
):
    """Get documents from a SharePoint document library."""
    logger.info("Entering get_sharepoint_documents", function="get_sharepoint_documents", drive_id=drive_id)

    try:
        from src.services.integrations.microsoft_graph.sharepoint_service import SharePointService

        # TODO: Implement token retrieval from user session or database
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Microsoft Graph integration requires user authentication token"
        )

        # access_token = await get_user_microsoft_token(current_user.id)
        # sharepoint_service = SharePointService(access_token)
        # documents = await sharepoint_service.list_documents(drive_id, folder_path)
        # await sharepoint_service.close()
        # return {"data": documents}

    except HTTPException:
        raise
    except Exception as e:
        logger.error("get_sharepoint_documents_failed", function="get_sharepoint_documents", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get SharePoint documents: {str(e)}"
        )


@router.post("/documents/sharepoint", response_model=CreateDocumentResponse, status_code=202)
async def create_document_from_sharepoint(
    body: dict,
    current_user: UserClaims = Depends(
        require_roles([
            UserRole.INTAKE_COORDINATOR, UserRole.DOC_SPECIALIST,
            UserRole.QC_OPERATOR, UserRole.PROOFREADER,
            UserRole.MANAGER, UserRole.ADMIN,
        ])
    ),
    db: AsyncSession = Depends(get_db),
):
    """Create Klara document from SharePoint file."""
    logger.info("Entering create_document_from_sharepoint", function="create_document_from_sharepoint")

    try:
        from src.services.integrations.microsoft_graph.sharepoint_service import SharePointService
        from uuid import UUID

        site_id = body.get("site_id")
        drive_id = body.get("drive_id")
        item_id = body.get("item_id")
        client_id = body.get("client_id")
        document_type = body.get("document_type", "quality_control")
        title = body.get("title")

        if not all([site_id, drive_id, item_id]):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing required fields: site_id, drive_id, item_id"
            )

        # TODO: Implement token retrieval from user session or database
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Microsoft Graph integration requires user authentication token"
        )

        # access_token = await get_user_microsoft_token(current_user.id)
        # sharepoint_service = SharePointService(access_token)
        #
        # # Download document from SharePoint
        # content, filename = await sharepoint_service.download_document(drive_id, item_id)
        # await sharepoint_service.close()
        #
        # # Create document record with SharePoint metadata
        # document_data = {
        #     "title": title or filename,
        #     "client_id": UUID(client_id) if client_id else None,
        #     "document_type": document_type,
        #     "storage_type": "sharepoint",
        #     "sharepoint_site_id": site_id,
        #     "sharepoint_drive_id": drive_id,
        #     "sharepoint_item_id": item_id,
        #     "blob_url": None,  # No local file
        # }
        #
        # # Create document and trigger AI analysis
        # result = await document_service.create_document_from_storage(
        #     db, document_data, content, actor_id=current_user.id
        # )
        #
        # logger.info("Exiting create_document_from_sharepoint", document_id=str(result.id))
        # return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error("create_document_from_sharepoint_failed", function="create_document_from_sharepoint", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create document from SharePoint: {str(e)}"
        )


@router.get("/{document_id}/word/config")
async def word_online_config(
    document_id: UUID,
    current_user: UserClaims = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return Word Online editor config for the frontend."""
    logger.info("Entering word_online_config", function="word_online_config", document_id=str(document_id))

    try:
        doc = await document_service.get_document(db, document_id)

        # Check if document is stored in SharePoint
        if doc.storage_type != "sharepoint":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Word Online integration requires SharePoint storage"
            )

        # TODO: Generate Word Online configuration
        # This would include:
        # - Document URL (webUrl from SharePoint)
        # - Access token for SharePoint access
        # - WOPI endpoint configuration
        # - User information for co-authoring

        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Word Online configuration not yet implemented"
        )

        # access_token = await get_user_microsoft_token(current_user.id)
        # sharepoint_service = SharePointService(access_token)
        # word_url = await sharepoint_service.get_word_online_edit_url(
        #     doc.sharepoint_drive_id,
        #     doc.sharepoint_item_id
        # )
        # await sharepoint_service.close()
        #
        # config = {
        #     "document": {
        #         "fileType": "docx",
        #         "key": str(document_id).replace("-", ""),
        #         "title": doc.title or "document.docx",
        #         "url": word_url,
        #         "permissions": {
        #             "edit": True,
        #             "read": False,
        #         }
        #     },
        #     "editorConfig": {
        #         "mode": "edit",
        #         "user": {
        #             "id": str(current_user.id),
        #             "name": current_user.display_name or "User",
        #         },
        #         "embedded": {
        #             "embedUrl": word_url,
        #             "sharePointId": doc.sharepoint_item_id,
        #             "accessToken": access_token,  # In production, this should be more secure
        #         }
        #     }
        # }
        # return config

    except HTTPException:
        raise
    except Exception as e:
        logger.error("word_online_config_failed", function="word_online_config", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate Word Online config: {str(e)}"
        )


@router.get("/{document_id}/word/file")
async def word_online_file(
    document_id: UUID,
    current_user: UserClaims = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Serve docx file from SharePoint for Word Online editing."""
    logger.info("Entering word_online_file", function="word_online_file", document_id=str(document_id))

    try:
        doc = await document_service.get_document(db, document_id)

        if doc.storage_type != "sharepoint":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Word Online integration requires SharePoint storage"
            )

        # TODO: Download and serve file from SharePoint
        # access_token = await get_user_microsoft_token(current_user.id)
        # sharepoint_service = SharePointService(access_token)
        # content, filename = await sharepoint_service.download_document(
        #     doc.sharepoint_drive_id,
        #     doc.sharepoint_item_id
        # )
        # await sharepoint_service.close()
        #
        # return Response(
        #     content=content,
        #     media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        #     headers={"Content-Disposition": f'attachment; filename="{filename}"'}
        # )

        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Word Online file serving not yet implemented"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("word_online_file_failed", function="word_online_file", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to serve Word Online file: {str(e)}"
        )


@router.post("/{document_id}/word/callback")
async def word_online_callback(
    document_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Word Online calls this when the user saves the document."""
    logger.info("Entering word_online_callback", function="word_online_callback", document_id=str(document_id))

    try:
        body = await request.json()
        status = body.get("status")

        logger.info("Word Online callback received", document_id=str(document_id), status=status)

        if status in (2, 6):  # Save required
            # TODO: Handle Word Online save callback
            # This would involve:
            # - Getting the updated content from Word Online
            # - Uploading it back to SharePoint
            # - Triggering any necessary processing

            logger.info("Word Online save callback - not yet implemented")
            return {"error": 0}

        return {"error": 0}

    except Exception as e:
        logger.error("word_online_callback_failed", function="word_online_callback", error=str(e))
        return {"error": 1, "message": str(e)}
