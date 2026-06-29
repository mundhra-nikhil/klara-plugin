# Comprehensive Debugging Guide

## 🔍 Debugging Text Replacement Issues

When "Accept" doesn't work, follow this systematic debugging approach:

### Step 1: Enable Detailed Logging

All detailed logging is now enabled by default. Open browser console (F12) to see:

- 🔍 Search attempts
- 📋 Paragraph content inspection
- 🎯 Match confirmation
- ✅ Success/failure status
- ⚠️ Warnings for partial issues
- ❌ Error messages

### Step 2: Test Word API Availability

In browser console, run:
```javascript
await Word.run(async (ctx) => {
  const body = ctx.document.body;
  ctx.load(body, 'text');
  await ctx.sync();
  console.log('Document text:', body.text);
});
```

### Step 3: Check What's Actually in the Paragraph

Use the debug function in browser console:
```javascript
await KlaraTestUtils.debugParagraphContent(23); // or any paragraph index
```

### Step 4: Test Special Character Handling

Special characters like §, ©, ®, ™ can have multiple Unicode representations:

```javascript
// Test section symbol search
await Word.run(async (ctx) => {
  const body = ctx.document.body;
  const results = body.search('§1234');
  ctx.load(results, 'items');
  await ctx.sync();
  console.log('Found:', results.items.length, 'items');
  if (results.items.length > 0) {
    console.log('Text found:', results.items[0].text);
  }
});
```

### Step 5: Run Test Suite

Execute comprehensive tests:
```javascript
await KlaraTestUtils.runTestSuite(KlaraTestUtils.specialCharacterTests);
```

## 🎯 Common Issues and Solutions

### Issue 1: "Could not find exact text"

**Possible Causes**:
- Special character encoding differences
- Hidden formatting characters
- Paragraph index misalignment
- Unicode normalization issues

**Solutions**:
1. Check paragraph content with debug function
2. Try manual search in Word document
3. Check for hidden formatting (show/hide ¶)
4. Use browser console to test different search variations

### Issue 2: "Paragraph index out of range"

**Possible Causes**:
- Tables/figures affect paragraph counting
- Empty paragraphs not counted consistently
- Document structure complexity

**Solutions**:
1. Use body search instead of paragraph-specific search
2. Check actual document structure
3. Log all paragraph indices to verify indexing

### Issue 3: Special Characters Not Found

**Possible Causes**:
- Unicode representation differences
- Font encoding issues
- Copy-paste encoding problems

**Solutions**:
1. Enhanced search now tries multiple character variations
2. Special character mappings include common alternatives
3. Wildcard search as final fallback
4. Manual verification of character codes

## 🧪 Testing Procedure

### Basic Testing
1. Create test document with known issues
2. Load document in Word with Klara add-in
3. Open browser console (F12)
4. Trigger "Accept" on specific suggestion
5. Check console logs for detailed process
6. Verify document was actually changed

### Advanced Testing
1. Use test utilities: `KlaraTestUtils.runTestCase(...)`
2. Create custom test cases for your specific issues
3. Run test suites: `KlaraTestUtils.runTestSuite(...)`
4. Analyze results and error patterns
5. Document findings in test results

### Performance Testing
```javascript
// Test multiple replacements performance
const startTime = Date.now();
// ... run multiple accept operations ...
console.log('Time taken:', Date.now() - startTime, 'ms');
```

## 📊 Understanding Console Logs

### Success Pattern
```
🔍 Searching for "§1234" in paragraph 23
📋 Paragraph 23 content: "According to §1234 Civil Code..."
🎯 Found text to replace: "§1234"
✅ Successfully replaced "§1234" with "§ 1234"
```

### Failure Pattern
```
🔍 Searching for "§1234" in paragraph 23
📋 Paragraph 23 content: "According to §1234 Civil Code..."
🔍 Exact search found: 0 results
🔍 Case-insensitive search found: 0 results
🔍 Relaxed search found: 0 results
❌ No search results found for "§1234" in paragraph 23
```

### Debug Information
```
🔍 Trying 3 search variations for "§1234"
🔍 Variation 1/3: "§1234"
🔍 Variation 2/3: "?1234"
🔍 Variation 3/3: "1234"
```

## 🛠️ Manual Verification Steps

1. **Visual Check**: Look at the document to see if text changed
2. **Search in Word**: Use Word's built-in search to find the text
3. **Character Inspection**: Check exact character codes:
   ```javascript
   "§1234".split('').map(c => c.charCodeAt(0));
   ```
4. **Paragraph Count**: Verify paragraph index is correct
5. **Show Formatting**: Toggle Word formatting marks (¶)

## 📝 Reporting Issues

When reporting text replacement issues, include:

1. **Exact error message** from browser console
2. **Console logs** showing the search process
3. **Text being searched** (original and replacement)
4. **Paragraph index** if applicable
5. **Document content** around the target text
6. **Special characters** involved
7. **Steps to reproduce** the issue
8. **Screenshots** if applicable

## 🔧 Advanced Debugging

### Inspect Word Object Model
```javascript
await Word.run(async (ctx) => {
  const doc = ctx.document;
  const props = doc.properties;
  ctx.load(props, ['title', 'author']);
  await ctx.sync();
  console.log('Document properties:', props);
});
```

### Test Search API Directly
```javascript
await Word.run(async (ctx) => {
  const body = ctx.document.body;
  // Test different search options
  const exact = body.search('text', { matchCase: true });
  const relaxed = body.search('text', { matchCase: false, ignorePunct: true });
  const wildcard = body.search('t?xt', { matchWildcards: true });
  ctx.load(exact, relaxed, wildcard, 'items');
  await ctx.sync();
  console.log('Exact:', exact.items.length);
  console.log('Relaxed:', relaxed.items.length);
  console.log('Wildcard:', wildcard.items.length);
});
```

### Monitor Document Events
```javascript
await Word.run(async (ctx) => {
  ctx.document.onContentControlAdded.add(() => {
    console.log('Content control added');
  });
  ctx.document.onParagraphAdded.add(() => {
    console.log('Paragraph added');
  });
});
```

## 📚 Quick Reference

### Console Commands
- `KlaraTestUtils.testWordApi()` - Test Word API availability
- `KlaraTestUtils.debugParagraphContent(n)` - Show paragraph content
- `KlaraTestUtils.runTestSuite(tests)` - Run multiple tests
- `KlaraTestUtils.createTestDocument()` - Create test document

### Enhanced Search Features
- Multiple search variations for special characters
- Unicode character normalization handling
- Wildcard search for pattern matching
- Fallback search strategies
- Paragraph and body-level search options

### Error Types
- **Search Failed**: Text not found in document
- **Index Error**: Paragraph index out of range
- **API Error**: Word API communication issue
- **Verification Failed**: Replacement didn't match expected result