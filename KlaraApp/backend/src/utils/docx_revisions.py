"""Accept (flatten) all tracked changes in a .docx.

When a client uploads a pleading it often still carries pending tracked changes
(a reviewing attorney's edits, prior AI suggestions, …). Before the QA engine
runs we want a single clean baseline, so we *accept* every revision:

  • <w:ins> / <w:moveTo>      → unwrap (the inserted/moved text becomes normal)
  • <w:del> / <w:moveFrom>    → drop entirely (the deleted text is gone)
  • <w:rPrChange>/<w:pPrChange>/<w:tblPrChange>/… → strip (keep current format)

This mirrors Word's "Accept All Changes". It runs over every body-bearing part
of the package (document, footnotes, endnotes, headers, footers, comments) and
rewrites the .docx in place, preserving all other zip entries verbatim.

Note: a *paragraph-mark* deletion (tracked merge of two paragraphs) is handled
by simply removing the revision mark — the paragraphs are kept separate rather
than merged. That edge case is rare in intake documents and keeping it safe
(no content loss) matters more than a perfectly faithful merge.
"""

import os
import shutil
import zipfile

from lxml import etree

from src.core.logger import get_logger_with_context

logger = get_logger_with_context()

_W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def _w(tag: str) -> str:
    return f"{{{_W}}}{tag}"


# Byte signatures of actual revision elements. NB: ``<w:ins`` alone would also
# match ``<w:insideH>`` / ``<w:insideV>`` (table-cell borders), so we match the
# element start precisely (``<w:ins `` with attrs or ``<w:ins>`` bare).
_REVISION_SIGNATURES = (
    b"<w:ins ", b"<w:ins>", b"<w:del ", b"<w:del>",
    b"<w:moveFrom", b"<w:moveTo", b"PrChange", b"numberingChange",
)


def _has_revision_bytes(blob: bytes) -> bool:
    return any(sig in blob for sig in _REVISION_SIGNATURES)


# Parts of an OOXML package that can contain run/paragraph revisions.
_REVISIONABLE = ("word/document.xml",)
_REVISIONABLE_PREFIXES = (
    "word/footnotes",
    "word/endnotes",
    "word/header",
    "word/footer",
    "word/comments",
)

# Revision wrappers whose *content is kept* (accepted insertion / move target).
_UNWRAP_TAGS = ("ins", "moveTo")
# Revision wrappers whose *content is removed* (accepted deletion / move source).
_DROP_TAGS = ("del", "moveFrom")
# Format-change records; removing them accepts the current formatting.
_CHANGE_TAGS = (
    "rPrChange", "pPrChange", "tblPrChange", "trPrChange",
    "tcPrChange", "sectPrChange", "tblGridChange", "numberingChange",
)


def _accept_tree(root) -> tuple[int, int, int]:
    """Accept all revisions in an lxml ``root`` in place.

    Returns (unwrapped, dropped, change_records_stripped)."""
    # 1) Drop deleted / move-source content first so it never survives.
    dropped = 0
    for tag in _DROP_TAGS:
        for el in list(root.iter(_w(tag))):
            parent = el.getparent()
            if parent is not None:
                parent.remove(el)
                dropped += 1

    # 2) Unwrap inserted / move-target content: splice children into the parent
    #    at the wrapper's position, preserving document order.
    unwrapped = 0
    for tag in _UNWRAP_TAGS:
        for el in list(root.iter(_w(tag))):
            parent = el.getparent()
            if parent is None:
                continue
            idx = parent.index(el)
            for child in list(el):
                el.remove(child)
                parent.insert(idx, child)
                idx += 1
            # Carry any tail text (rare inside these wrappers) onto a sibling.
            parent.remove(el)
            unwrapped += 1

    # 3) Strip format-change records (accept current run/paragraph formatting).
    changes = 0
    for tag in _CHANGE_TAGS:
        for el in list(root.iter(_w(tag))):
            parent = el.getparent()
            if parent is not None:
                parent.remove(el)
                changes += 1

    return unwrapped, dropped, changes


def _is_revisionable(name: str) -> bool:
    if name in _REVISIONABLE:
        return True
    return name.endswith(".xml") and name.startswith(_REVISIONABLE_PREFIXES)


def document_has_revisions(path: str) -> bool:
    """Cheap check: does the .docx carry any pending tracked changes?"""
    if not path or not os.path.exists(path):
        return False
    try:
        with zipfile.ZipFile(path) as z:
            for name in z.namelist():
                if not _is_revisionable(name):
                    continue
                if _has_revision_bytes(z.read(name)):
                    return True
    except Exception as e:  # corrupt/zip error — treat as "no revisions"
        logger.warning(f"revision check failed for {path}: {e}")
    return False


def accept_all_revisions(path: str) -> dict:
    """Accept every tracked change in the .docx at ``path``, rewriting it in
    place. Safe no-op (returns counts of 0) when the file has no revisions or
    isn't a .docx. Returns a summary dict.

    The rewrite is atomic-ish: we build the new package in a temp file beside the
    original and replace it only on success, so a failure can't truncate the
    user's document."""
    summary = {"changed": False, "parts": 0, "unwrapped": 0, "dropped": 0, "format_changes": 0}
    if not path or not os.path.exists(path) or not path.lower().endswith(".docx"):
        return summary

    try:
        with zipfile.ZipFile(path) as zin:
            names = zin.namelist()
            entries = {name: zin.read(name) for name in names}
    except Exception as e:
        logger.error(f"accept_all_revisions: cannot read {path}: {e}")
        return summary

    parser = etree.XMLParser(remove_blank_text=False, recover=False)
    touched = 0
    for name in names:
        if not _is_revisionable(name):
            continue
        blob = entries[name]
        if not _has_revision_bytes(blob):
            continue
        try:
            root = etree.fromstring(blob, parser=parser)
        except Exception as e:
            logger.warning(f"accept_all_revisions: skip unparyable part {name}: {e}")
            continue
        u, d, c = _accept_tree(root)
        if u or d or c:
            entries[name] = etree.tostring(
                root, xml_declaration=True, encoding="UTF-8", standalone=True
            )
            touched += 1
            summary["unwrapped"] += u
            summary["dropped"] += d
            summary["format_changes"] += c

    if touched == 0:
        return summary

    tmp = path + ".accepted.tmp"
    try:
        with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zout:
            for name in names:
                zout.writestr(name, entries[name])
        shutil.move(tmp, path)
    except Exception as e:
        logger.error(f"accept_all_revisions: failed to rewrite {path}: {e}")
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass
        return summary

    summary["changed"] = True
    summary["parts"] = touched
    logger.info(
        "Accepted pending tracked changes on upload",
        path=path, parts=touched,
        unwrapped=summary["unwrapped"], dropped=summary["dropped"],
        format_changes=summary["format_changes"],
    )
    return summary
