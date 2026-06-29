"""Render a .docx to page images so a vision model can evaluate rendered-layout
rules (margins, line numbers, page numbering, widows/orphans, footnote flow)
that are not reliably verifiable from the document XML or plain text.

Pipeline: docx --(LibreOffice headless)--> PDF --(pdf2image / poppler)--> PNG[].
Both LibreOffice and poppler are installed in the backend image. All failures
are swallowed and return an empty list so the engine falls back gracefully.
"""

import os
import shutil
import subprocess
import tempfile

from src.core.logger import get_logger_with_context

logger = get_logger_with_context()


def _soffice_bin() -> str | None:
    return shutil.which("soffice") or shutil.which("libreoffice")


def render_available() -> bool:
    """True if the rendering toolchain (LibreOffice) is present."""
    return _soffice_bin() is not None


def docx_to_pdf(path: str, out_dir: str) -> str | None:
    """Convert a .docx to PDF using headless LibreOffice. Returns the PDF path."""
    soffice = _soffice_bin()
    if not soffice or not os.path.exists(path):
        return None
    try:
        # A dedicated profile dir avoids clashes when soffice runs concurrently.
        profile = os.path.join(out_dir, "lo_profile")
        subprocess.run(
            [
                soffice, "--headless", "--norestore",
                f"-env:UserInstallation=file://{profile}",
                "--convert-to", "pdf", "--outdir", out_dir, path,
            ],
            check=True,
            capture_output=True,
            timeout=90,
        )
        base = os.path.splitext(os.path.basename(path))[0] + ".pdf"
        pdf_path = os.path.join(out_dir, base)
        return pdf_path if os.path.exists(pdf_path) else None
    except Exception as e:
        logger.warning(f"LibreOffice docx→pdf failed for {path}: {e}")
        return None


def render_docx_to_images(path: str, max_pages: int = 6, dpi: int = 130) -> list[bytes]:
    """Render the first ``max_pages`` pages of a .docx to PNG bytes.

    Returns [] if the toolchain is unavailable or rendering fails — callers must
    treat an empty list as "vision analysis unavailable" and fall back."""
    if not render_available():
        logger.info("LibreOffice not available; skipping vision render")
        return []
    try:
        from pdf2image import convert_from_path
    except Exception as e:
        logger.warning(f"pdf2image unavailable: {e}")
        return []

    with tempfile.TemporaryDirectory() as tmp:
        pdf_path = docx_to_pdf(path, tmp)
        if not pdf_path:
            return []
        try:
            images = convert_from_path(pdf_path, dpi=dpi, last_page=max_pages)
        except Exception as e:
            logger.warning(f"pdf2image conversion failed for {pdf_path}: {e}")
            return []

        out: list[bytes] = []
        import io
        for img in images[:max_pages]:
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            out.append(buf.getvalue())
        logger.info(f"Rendered {len(out)} page image(s) for vision analysis")
        return out
