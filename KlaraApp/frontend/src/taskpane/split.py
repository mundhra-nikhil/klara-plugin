import os
import re

src_file = r"C:\Users\Int202613\Documents\Github\Klara\klara-plugin\KlaraApp\frontend\src\taskpane\word-context.ts"
out_dir = r"C:\Users\Int202613\Documents\Github\Klara\klara-plugin\KlaraApp\frontend\src\taskpane\word"

os.makedirs(out_dir, exist_ok=True)

with open(src_file, 'r', encoding='utf-8') as f:
    content = f.read()

# We will define what goes into what file
files = {
    'utils.ts': [
        'escapeRegExp',
        'generateSearchVariations',
        'searchRobust',
        'searchWithVariations',
        'findParagraphIndexByText',
        'stripFormatting'
    ],
    'selection.ts': [
        'searchAndSelect',
        'selectParagraph',
        'highlightRange',
        'clearHighlights'
    ],
    'replace.ts': [
        'TextReplacementResult',
        'replaceTextInParagraph',
        'replaceText',
        'undoDirectReplacement'
    ],
    'formatting.ts': [
        'FormattingResult',
        'applyParagraphFormatting',
        'searchAndApplyFormatting',
        'applyGlobalFormatting'
    ],
    'comments.ts': [
        'createKlaraComment',
        'createKlaraCommentInParagraph',
        'createKlaraCommentAtParagraph'
    ],
    'tracking.ts': [
        'SIMULATED_DELETION_PREFIX',
        'SIMULATED_DELETION_SUFFIX',
        'SIMULATED_INSERTION_PREFIX',
        'SIMULATED_INSERTION_SUFFIX',
        'createSimulatedTrackedChange',
        'createSimulatedTrackedChangeInParagraph',
        'acceptSimulatedTrackedChange',
        'rejectSimulatedTrackedChange',
        'undoSimulatedTrackedChange',
        'extractSimulatedChange'
    ],
    'metadata.ts': [
        'getDocumentMetadata',
        'getDocumentSelection',
        'getActiveDocumentData',
        'testWordApiAvailability'
    ]
}

def extract_block(text, start_index):
    # Find the first '{'
    brace_index = text.find('{', start_index)
    if brace_index == -1:
        # maybe it's a const without brace, like a string?
        semicolon_index = text.find(';', start_index)
        return text[start_index:semicolon_index+1], semicolon_index+1

    # Count braces
    count = 0
    in_string = False
    string_char = ''
    in_comment = False
    in_line_comment = False
    
    i = brace_index
    while i < len(text):
        char = text[i]
        
        if in_line_comment:
            if char == '\n':
                in_line_comment = False
            i += 1
            continue
            
        if in_comment:
            if char == '*' and i+1 < len(text) and text[i+1] == '/':
                in_comment = False
                i += 2
                continue
            i += 1
            continue
            
        if in_string:
            if char == '\\':
                i += 2 # skip escaped char
                continue
            if char == string_char:
                in_string = False
            i += 1
            continue
            
        if char == '"' or char == "'" or char == '`':
            in_string = True
            string_char = char
            i += 1
            continue
            
        if char == '/' and i+1 < len(text) and text[i+1] == '/':
            in_line_comment = True
            i += 2
            continue
            
        if char == '/' and i+1 < len(text) and text[i+1] == '*':
            in_comment = True
            i += 2
            continue
            
        if char == '{':
            count += 1
        elif char == '}':
            count -= 1
            if count == 0:
                return text[start_index:i+1], i+1
                
        i += 1
                
    return None, -1

files['utils.ts'].append('isNormalizedMatch')

matches = list(re.finditer(r'(?:export\s+)?(?:async\s+)?(?:function|const|interface|type)\s+([A-Za-z0-9_]+)', content))

blocks = {}
for match in matches:
    name = match.group(1)
    start_idx = match.start()
    
    jsdoc_match = re.search(r'/\*\*[\s\S]*?\*/\s*$', content[:match.start()])
    if jsdoc_match:
        start_idx = jsdoc_match.start()
        
    block, end_idx = extract_block(content, match.start())
    if block:
        full_block = content[start_idx:match.start()] + block
        blocks[name] = full_block

for file_name, func_names in files.items():
    file_path = os.path.join(out_dir, file_name)
    with open(file_path, 'w', encoding='utf-8') as f:
        # Basic imports - we will just include Word types assuming Word is ambient, 
        # but wait, Word might be ambient. We will let TypeScript handle imports or we manually fix them next.
        
        for name in func_names:
            if name in blocks:
                block_content = blocks[name]
                if not block_content.strip().startswith('export '):
                    # inject export
                    block_content = re.sub(r'^(/\*\*[\s\S]*?\*/\s*)?(async\s+)?(function|const|interface|type)', r'\1export \2\3', block_content)
                f.write(block_content + '\n\n')
            else:
                print(f"MISSING: {name}")

with open(os.path.join(out_dir, 'index.ts'), 'w', encoding='utf-8') as f:
    for file_name in files.keys():
        if file_name != 'index.ts':
            module_name = file_name.replace('.ts', '')
            f.write(f'export * from "./{module_name}";\n')

print("Done generating files!")
