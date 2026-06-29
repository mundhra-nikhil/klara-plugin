# Klara Test Document Template

This document serves as a template for creating test documents to debug text replacement issues in the Klara Word Add-in.

## Test Document Structure

### Section 1: Special Character Tests
- §1234 → § 1234 (section symbol spacing)
- ©2024 → © 2024 (copyright symbol)
- Microsoft® (registered trademark)
- Klara™ (trademark symbol)

### Section 2: Number Formatting
- 1. First item
- 2. Second item
- 3. Third item

### Section 3: Citation Tests
- [1] Reference one
- [2] Reference two
- [3] Reference three

### Section 4: Spacing Tests
- word1,word2 → word1, word2
- (test) → ( test )
- "quoted" → " quoted "

### Section 5: Mixed Content
- Legal citation: §1234 Civil Code
- Copyright: ©2024 Company Name
- Reference: See [1] for details
- Numbered: 1. First, 2. Second, 3. Third

## How to Use This Template

1. Copy this content to a new Word document
2. Save it in this test-debug folder
3. Use it for testing specific text replacement scenarios
4. Check browser console (F12) for detailed logs
5. Verify each replacement works correctly

## Current Debug Focus

**Special Characters**: Section symbol (§) not being found during search.

**Test Steps**:
1. Open the test document in Word
2. Open Klara add-in task pane
3. Open browser console (F12)
4. Try "Accept" on suggestions with § symbol
5. Check console logs for detailed search process
6. Verify text was actually replaced in document