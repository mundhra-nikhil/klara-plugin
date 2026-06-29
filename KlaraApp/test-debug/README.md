# Test Debug Folder

This folder is dedicated to testing and debugging the Klara Word Add-in, specifically for document editing and text replacement functionality.

## Purpose

- Test text replacement with special characters (§, ©, ®, ™, etc.)
- Debug search functionality issues
- Test paragraph indexing accuracy
- Validate Word API interactions

## Test Documents

Place your test Word documents here for debugging text replacement issues.

## Current Debugging Focus

**Issue**: Section symbol (§) and other special characters not being found during text replacement.

**Test Cases**:
- §1234 → § 1234 (section symbol spacing)
- Copyright symbols and variations
- Special Unicode characters in legal documents
- Paragraph indexing accuracy

## Debugging Tools

Use the enhanced logging in `../src/taskpane/word-context.ts` which now includes:
- 🔍 Search attempt logging
- 📋 Paragraph content inspection
- 🎯 Match found confirmation
- ✅ Success/failure indicators
- ⚠️ Warning messages for partial failures
- ❌ Error messages for complete failures

## How to Use

1. Copy test documents to this folder
2. Open browser console (F12) for detailed logging
3. Use the "Accept" button on suggestions
4. Check console output for detailed search/replacement logs
5. Verify changes in Word document

## Test Results Template

```
Test Case: [Description]
Text: "Original"
Expected: "Replacement"
Result: [Success/Failed]
Console Output: [Relevant logs]
```