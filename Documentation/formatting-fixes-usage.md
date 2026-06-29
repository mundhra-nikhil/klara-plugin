# Formatting Fixes Usage

This document explains how to use the automated formatting fixes feature in the Klara Word add-in.

## Overview

The Klara add-in now supports automated paragraph formatting fixes through the "Accept" button, similar to how text replacements work. This allows users to quickly fix common formatting issues like:

- "Keep with next" settings for headings
- Page break settings
- Widow/orphan control
- Line spacing
- Paragraph alignment

## Backend Implementation

### Finding Format

To enable automated formatting fixes, the backend should return findings with the following structure:

```json
{
  "id": "finding-123",
  "type": "format",
  "severity": "major",
  "title": "Heading orphan / keepNext",
  "description": "Section heading at paragraph 20 has 'keep with next' disabled — risk of an orphan heading at a page break.",
  "paragraph_index": 20,
  "formatting_fix": {
    "type": "keep_with_next",
    "value": true,
    "description": "Enable 'Keep with next' to prevent orphan headings"
  }
}
```

### Supported Formatting Operations

#### 1. Keep with Next
```json
{
  "formatting_fix": {
    "type": "keep_with_next",
    "value": true,
    "description": "Enable 'Keep with next' to prevent orphan headings"
  }
}
```

#### 2. Page Break Before
```json
{
  "formatting_fix": {
    "type": "page_break_before",
    "value": true,
    "description": "Add page break before heading"
  }
}
```

#### 3. Widow/Orphan Control
```json
{
  "formatting_fix": {
    "type": "widow_orphan_control",
    "value": true,
    "description": "Enable widow/orphan control"
  }
}
```

#### 4. Line Spacing
```json
{
  "formatting_fix": {
    "type": "line_spacing",
    "value": 1.5,
    "description": "Set line spacing to 1.5"
  }
}
```

#### 5. Alignment
```json
{
  "formatting_fix": {
    "type": "alignment",
    "value": "centered",
    "description": "Center align the heading"
  }
}
```

**Supported alignment values:** `'left'`, `'right'`, `'centered'`, `'justified'`

Note: `'distributed'` is not supported in Word API and will fall back to `'left'`.

## Frontend Implementation

### User Experience

1. **Navigation**: Users click on a formatting finding to navigate to the affected paragraph
2. **Visual Feedback**: The paragraph is highlighted with the appropriate color based on severity
3. **Accept Button**: Clicking "Accept" applies the formatting change automatically
4. **Confirmation**: Success message is displayed and the paragraph is highlighted in green

### Finding Display

Format findings appear in the suggestions list with:
- Title and description
- "Accept" button (primary action)
- "Reject" button
- "Comment" button

### Batch Operations

The "Accept All" button handles both text replacements and formatting fixes:
- Text replacements are applied first
- Formatting fixes are applied second
- Summary message shows breakdown of changes

## Example: Complete Finding Flow

### 1. Detection (Backend)
```python
# Backend detects a heading without "keep with next"
finding = {
    "id": "format-001",
    "type": "format",
    "severity": "major",
    "title": "Heading orphan / keepNext",
    "description": "Section heading at paragraph 20 has 'keep with next' disabled — risk of an orphan heading at a page break.",
    "paragraph_index": 20,
    "confidence": 0.95,
    "formatting_fix": {
        "type": "keep_with_next",
        "value": true,
        "description": "Enable 'Keep with next' to prevent orphan headings"
    }
}
```

### 2. User Interaction (Frontend)
1. User sees the finding in the suggestions list
2. User clicks the finding card to navigate to paragraph 20
3. User reviews the highlighted heading
4. User clicks "Accept"

### 3. Application (Word API)
```typescript
// Frontend calls the Word API
const result = await applyParagraphFormatting(20, {
    type: 'keep_with_next',
    value: true
});
```

### 4. Result
- "Keep with next" is enabled for the heading
- Finding is marked as "accepted" in the backend
- Success message is displayed
- Paragraph is highlighted in green to confirm the change

## Technical Details

### Word API Functions

The implementation provides two main functions:

1. **`applyParagraphFormatting(paragraphIndex, operation)`**
   - Applies formatting to a specific paragraph by index
   - Use when paragraph index is known

2. **`searchAndApplyFormatting(searchText, operation)`**
   - Searches for text and applies formatting to the containing paragraph
   - Use when paragraph index is unknown but text is known

### Error Handling

- Handles missing paragraph index gracefully
- Falls back to text search if paragraph index is unavailable
- Provides clear error messages for invalid operations
- Validates formatting operation types and values

### Result Tracking

All formatting operations return:
```typescript
{
  success: boolean;
  applied: boolean;
  message: string;
  paragraphIndex?: number;
}
```

## Migration Notes

### Existing Text Replacement Findings
No changes needed - existing text replacement findings continue to work as before.

### Mixed Findings
A finding can have both text replacement and formatting fix, but currently the system prioritizes one or the other based on availability:
- If `formatting_fix` is present, it uses the formatting handler
- If `original_text` and `replacement_text` are present, it uses the text replacement handler

### Future Enhancements
Potential improvements:
- Support for character-level formatting (bold, italic, etc.)
- Support for style application
- Support for table formatting
- Batch formatting with preview
- Undo functionality

## Testing

To test the formatting fixes:

1. Create a Word document with headings
2. Ensure some headings lack "Keep with next" setting
3. Run the Klara analysis
4. Verify findings appear with "Accept" buttons
5. Click "Accept" on a formatting finding
6. Verify the formatting is applied
7. Check the finding is marked as resolved

## Troubleshooting

**Issue**: "Accept" button doesn't appear for formatting findings
- **Solution**: Verify `formatting_fix` field is properly structured in the finding

**Issue**: Formatting is not applied
- **Solution**: Check that paragraph_index is correct and the operation type is supported

**Issue**: Wrong paragraph is formatted
- **Solution**: Verify paragraph index matches the actual document structure

**Issue**: Batch accept fails for formatting
- **Solution**: Check that all findings in the batch have valid paragraph indices or search text
