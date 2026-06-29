import os
import zipfile
import pytest
import xml.etree.ElementTree as ET
from src.utils.text_extractor import (
    accept_all_tracked_changes,
    compute_rule_violations,
)
from src.services.ai_jobs.ai_job_service import _synthesise_findings_from_precomputed

W_NS = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'

def test_accept_all_tracked_changes(tmp_path):
    # Create a dummy docx with tracked changes (insertions/deletions)
    docx_file = tmp_path / "test_revs.docx"
    
    # Minimal document.xml content with tracked changes
    xml_content = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
    <w:document xmlns:w="{W_NS}">
        <w:body>
            <w:p>
                <w:r><w:t>This is </w:t></w:r>
                <w:ins w:id="0" w:author="Author" w:date="2026-06-06T12:00:00Z">
                    <w:r><w:t>inserted </w:t></w:r>
                </w:ins>
                <w:del w:id="1" w:author="Author" w:date="2026-06-06T12:00:00Z">
                    <w:r><w:t>deleted </w:t></w:r>
                </w:del>
                <w:r><w:t>text.</w:t></w:r>
            </w:p>
        </w:body>
    </w:document>
    """
    
    with zipfile.ZipFile(docx_file, 'w') as z:
        z.writestr('word/document.xml', xml_content)
        
    # Run the accept tracked changes utility
    accept_all_tracked_changes(str(docx_file))
    
    # Read the processed XML back and check content
    with zipfile.ZipFile(docx_file, 'r') as z:
        processed_xml = z.read('word/document.xml')
        
    root = ET.fromstring(processed_xml)
    
    # Assert that ins elements are promoted, del elements are removed
    ins_tags = list(root.iter(f'{{{W_NS}}}ins'))
    del_tags = list(root.iter(f'{{{W_NS}}}del'))
    
    assert len(ins_tags) == 0
    assert len(del_tags) == 0
    
    # Reconstruct plain text to verify "This is inserted text." is present
    text_parts = []
    for t in root.iter(f'{{{W_NS}}}t'):
        text_parts.append(t.text or '')
    full_text = "".join(text_parts)
    assert "inserted" in full_text
    assert "deleted" not in full_text


def test_rule_15_spelling_and_grammar():
    # Pass a structured document containing spelling and repeated words
    structured = {
        "doc_default_font_size_pt": 12,
        "paragraphs": [
            {
                "index": 0,
                "text": "The organisation is planning a new project here.",
                "is_heading": False,
                "font_sizes_pt": [12],
                "alignment": "justify",
            },
            {
                "index": 1,
                "text": "This is a repeated word the the in this sentence.",
                "is_heading": False,
                "font_sizes_pt": [12],
                "alignment": "justify",
            }
        ],
        "footnotes": [],
    }
    
    violations = compute_rule_violations(structured)
    v15 = violations["violations"]["rule_15_spelling"]
    
    # Assert spelling violation is caught
    spelling_viols = [v for v in v15 if v["type"] == "spelling_typo"]
    assert len(spelling_viols) == 1
    assert spelling_viols[0]["original"] == "organisation"
    assert spelling_viols[0]["replacement"] == "organization"
    
    # Assert repeated word violation is caught
    repeated_viols = [v for v in v15 if v["type"] == "repeated_word"]
    assert len(repeated_viols) == 1
    assert repeated_viols[0]["original"] == "the the"
    assert repeated_viols[0]["replacement"] == "the"


def test_synthesise_rule_15_findings():
    violations = {
        "violations": {
            "rule_15_spelling": [
                {
                    "paragraph": 3,
                    "snippet": "some organisation text...",
                    "original": "organisation",
                    "replacement": "organization",
                }
            ]
        }
    }
    
    rules_meta = {
        15: {
            "name": "Spelling & grammar",
            "track": 3,
            "type": "spelling",
            "severity": "minor"
        }
    }
    
    findings = _synthesise_findings_from_precomputed(violations, rules_meta=rules_meta)
    
    assert len(findings) == 1
    assert findings[0]["rule_id"] == 15
    assert findings[0]["location"]["paragraph"] == 3
    assert findings[0]["original_text"] == "organisation"
    assert findings[0]["replacement_text"] == "organization"
