# Formatting Fixes - Backend Examples

This file provides concrete examples of how the backend should generate formatting fix findings for the Klara Word add-in.

## Example 1: Keep with Next for Headings

### Scenario
A heading at paragraph 20 has "Keep with next" disabled, risking an orphan heading at a page break.

### Backend Finding Generation
```python
def detect_orphan_headings(document):
    """Detect headings without 'keep with next' setting"""
    findings = []
    
    for i, paragraph in enumerate(document.paragraphs):
        if is_heading(paragraph) and not paragraph.format.keep_with_next:
            finding = {
                "id": f"orphan-heading-{i}",
                "type": "format",
                "severity": "major",
                "status": "open",
                "title": f"Heading orphan / keepNext",
                "description": f"Section heading at paragraph {i} has 'keep with next' disabled — risk of an orphan heading at a page break. When we get suggestions like these, the user can now simply click 'Accept' to fix this automatically.",
                "paragraph_index": i,
                "confidence": 0.95,
                "rule_name": "heading_keep_with_next",
                "formatting_fix": {
                    "type": "keep_with_next",
                    "value": True,
                    "description": "Enable 'Keep with next' to prevent orphan headings"
                }
            }
            findings.append(finding)
    
    return findings
```

### Expected Finding Output
```json
{
  "id": "orphan-heading-20",
  "type": "format",
  "severity": "major",
  "status": "open",
  "title": "Heading orphan / keepNext",
  "description": "Section heading at paragraph 20 has 'keep with next' disabled — risk of an orphan heading at a page break. When we get suggestions like these, the user can now simply click 'Accept' to fix this automatically.",
  "paragraph_index": 20,
  "confidence": 0.95,
  "rule_name": "heading_keep_with_next",
  "formatting_fix": {
    "type": "keep_with_next",
    "value": true,
    "description": "Enable 'Keep with next' to prevent orphan headings"
  }
}
```

## Example 2: Widow/Orphan Control

### Scenario
Body paragraphs lack widow/orphan control, which can cause single lines to appear at the top/bottom of pages.

### Backend Finding Generation
```python
def detect_widow_orphan_issues(document):
    """Detect paragraphs without widow/orphan control"""
    findings = []
    
    for i, paragraph in enumerate(document.paragraphs):
        if is_body_text(paragraph) and not paragraph.format.widow_control:
            finding = {
                "id": f"widow-orphan-{i}",
                "type": "format",
                "severity": "minor",
                "status": "open",
                "title": f"Widow/orphan control disabled",
                "description": f"Paragraph {i} has widow/orphan control disabled — risk of single lines appearing at page breaks.",
                "paragraph_index": i,
                "confidence": 0.90,
                "rule_name": "widow_orphan_control",
                "formatting_fix": {
                    "type": "widow_orphan_control",
                    "value": True,
                    "description": "Enable widow/orphan control to prevent orphan lines"
                }
            }
            findings.append(finding)
    
    return findings
```

## Example 3: Line Spacing Issues

### Scenario
Paragraphs have inconsistent line spacing (e.g., single spacing instead of double).

### Backend Finding Generation
```python
def detect_line_spacing_issues(document):
    """Detect paragraphs with incorrect line spacing"""
    findings = []
    
    for i, paragraph in enumerate(document.paragraphs):
        if paragraph.format.line_spacing != 2.0:  # Expected double spacing
            finding = {
                "id": f"line-spacing-{i}",
                "type": "format",
                "severity": "minor",
                "status": "open",
                "title": f"Incorrect line spacing",
                "description": f"Paragraph {i} has {paragraph.format.line_spacing} spacing instead of required 2.0 (double spacing).",
                "paragraph_index": i,
                "confidence": 0.95,
                "rule_name": "line_spacing",
                "formatting_fix": {
                    "type": "line_spacing",
                    "value": 2.0,
                    "description": "Set line spacing to 2.0 (double spacing)"
                }
            }
            findings.append(finding)
    
    return findings
```

## Example 4: Page Break Before Headings

### Scenario
Major headings should have a page break before them, but some are missing this setting.

### Backend Finding Generation
```python
def detect_missing_page_breaks(document):
    """Detect major headings without page break before"""
    findings = []
    
    for i, paragraph in enumerate(document.paragraphs):
        if is_major_heading(paragraph) and not paragraph.format.page_break_before:
            finding = {
                "id": f"page-break-{i}",
                "type": "format",
                "severity": "suggestion",
                "status": "open",
                "title": f"Missing page break before major heading",
                "description": f"Major heading at paragraph {i} should start on a new page.",
                "paragraph_index": i,
                "confidence": 0.85,
                "rule_name": "page_break_before_heading",
                "formatting_fix": {
                    "type": "page_break_before",
                    "value": True,
                    "description": "Add page break before major heading"
                }
            }
            findings.append(finding)
    
    return findings
```

## Example 5: Alignment Issues

### Scenario
Center-aligned headings are incorrectly left-aligned.

### Backend Finding Generation
```python
def detect_alignment_issues(document):
    """Detect headings with incorrect alignment"""
    findings = []
    
    for i, paragraph in enumerate(document.paragraphs):
        if is_center_heading(paragraph) and paragraph.format.alignment != "center":
            finding = {
                "id": f"alignment-{i}",
                "type": "format",
                "severity": "major",
                "status": "open",
                "title": f"Incorrect heading alignment",
                "description": f"Heading at paragraph {i} should be center-aligned but is currently {paragraph.format.alignment}.",
                "paragraph_index": i,
                "confidence": 0.95,
                "rule_name": "heading_alignment",
                "formatting_fix": {
                    "type": "alignment",
                    "value": "center",
                    "description": "Center align the heading"
                }
            }
            findings.append(finding)
    
    return findings
```

## Example 6: Mixed Text and Formatting Finding

### Scenario
A finding that requires both text replacement and formatting fix.

### Backend Finding Generation
```python
def create_comprehensive_finding(document):
    """Create a finding with both text and formatting issues"""
    
    finding = {
        "id": "comprehensive-001",
        "type": "format",
        "severity": "major",
        "status": "open",
        "title": "Heading formatting issue",
        "description": "Heading has both incorrect text and missing 'keep with next' setting.",
        "paragraph_index": 15,
        "original_text": "Incorrect Heading Text",
        "replacement_text": "Correct Heading Text",
        "confidence": 0.95,
        "rule_name": "heading_comprehensive_fix",
        # Note: The system will prioritize one fix or the other
        # For this case, we might create separate findings
    }
    
    return finding
```

## Integration with Existing QC System

### Example: Full QC Check Integration

```python
async def run_formatting_qc_check(document_id: str, document_content):
    """Run a formatting QC check and return findings"""
    
    findings = []
    
    # Run various formatting checks
    findings.extend(detect_orphan_headings(document_content))
    findings.extend(detect_widow_orphan_issues(document_content))
    findings.extend(detect_line_spacing_issues(document_content))
    findings.extend(detect_missing_page_breaks(document_content))
    findings.extend(detect_alignment_issues(document_content))
    
    # Store findings in database
    for finding in findings:
        await save_finding_to_db(
            document_id=document_id,
            finding_type=finding["type"],
            severity=finding["severity"],
            title=finding["title"],
            description=finding["description"],
            paragraph_index=finding["paragraph_index"],
            formatting_fix=finding["formatting_fix"],
            confidence=finding["confidence"],
            rule_name=finding["rule_name"]
        )
    
    return findings
```

## API Response Format

### GET /api/qc/findings?document_id=123

```json
{
  "findings": [
    {
      "id": "orphan-heading-20",
      "document_id": "123",
      "review_id": "review-001",
      "type": "format",
      "severity": "major",
      "status": "open",
      "title": "Heading orphan / keepNext",
      "description": "Section heading at paragraph 20 has 'keep with next' disabled — risk of an orphan heading at a page break.",
      "paragraph_index": 20,
      "confidence": 0.95,
      "rule_name": "heading_keep_with_next",
      "formatting_fix": {
        "type": "keep_with_next",
        "value": true,
        "description": "Enable 'Keep with next' to prevent orphan headings"
      }
    }
  ]
}
```

## Testing Examples

### Test Case 1: Single Formatting Fix
```python
def test_keep_with_next_fix():
    finding = {
        "id": "test-001",
        "type": "format",
        "severity": "major",
        "title": "Test heading fix",
        "description": "Test description",
        "paragraph_index": 5,
        "formatting_fix": {
            "type": "keep_with_next",
            "value": True
        }
    }
    
    # Frontend should:
    # 1. Display finding with Accept button
    # 2. Apply keep_with_next to paragraph 5 when Accept is clicked
    # 3. Mark finding as accepted in backend
    assert finding["formatting_fix"]["type"] == "keep_with_next"
    assert finding["paragraph_index"] == 5
```

### Test Case 2: Batch Formatting Fixes
```python
def test_batch_formatting_fixes():
    findings = [
        {
            "id": "test-001",
            "type": "format",
            "severity": "major",
            "paragraph_index": 5,
            "formatting_fix": {
                "type": "keep_with_next",
                "value": True
            }
        },
        {
            "id": "test-002",
            "type": "format",
            "severity": "minor",
            "paragraph_index": 10,
            "formatting_fix": {
                "type": "widow_orphan_control",
                "value": True
            }
        }
    ]
    
    # Frontend should:
    # 1. Apply both formatting fixes when Accept All is clicked
    # 2. Display summary message
    # 3. Mark both findings as accepted
    assert len(findings) == 2
```

## Error Handling Examples

### Invalid Paragraph Index
```python
# Bad example - paragraph index out of range
bad_finding = {
    "paragraph_index": 999999,  # Invalid index
    "formatting_fix": {
        "type": "keep_with_next",
        "value": True
    }
}

# Frontend should handle gracefully with error message
# "Paragraph index 999999 out of range"
```

### Missing Formatting Fix
```python
# Bad example - missing formatting_fix field
incomplete_finding = {
    "paragraph_index": 5,
    # Missing formatting_fix field
}

# Frontend should:
# 1. Not show Accept button
# 2. Show as non-actionable finding
```

### Unsupported Operation Type
```python
# Bad example - unsupported operation type
invalid_finding = {
    "paragraph_index": 5,
    "formatting_fix": {
        "type": "unsupported_operation",
        "value": True
    }
}

# Frontend should:
# 1. Show error message
# 2. "Unknown formatting operation type: unsupported_operation"
```

## Summary

These examples demonstrate how to properly format findings for automated formatting fixes in the Klara Word add-in. The key components are:

1. **Format type**: Set to "format" for formatting issues
2. **Paragraph index**: Specify the target paragraph
3. **Formatting fix object**: Define the operation type and value
4. **Clear description**: Help users understand the issue and fix

The frontend will handle the rest, providing users with one-click fixes for common formatting problems.
