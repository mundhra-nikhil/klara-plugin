import os
import re

src_file = r"C:\Users\Int202613\Documents\Github\Klara\klara-plugin\KlaraApp\frontend\src\taskpane\word-context.ts"
out_dir = r"C:\Users\Int202613\Documents\Github\Klara\klara-plugin\KlaraApp\frontend\src\taskpane\word"

os.makedirs(out_dir, exist_ok=True)

with open(src_file, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# We will group lines into blocks
blocks = []
current_block = []
current_name = None

def get_def_name(line):
    # Regex to match function, const, interface, type
    m = re.match(r'^(?:export\s+)?(?:async\s+)?(?:function|const|interface|type)\s+([A-Za-z0-9_]+)', line)
    if m:
        return m.group(1)
    return None

for i, line in enumerate(lines):
    # Check if this line is the start of a definition
    name = get_def_name(line)
    if name and not line.startswith(' '):
        # We found a definition! 
        # Wait, if there was a jsdoc, it should be part of this block.
        # But we already added it to current_block. So we just name the current block!
        if current_name is None:
            current_name = name
        else:
            # We already have a name? That means we had multiple definitions in one block?
            # Or we found a new definition without a preceding jsdoc being captured correctly.
            # Actually, let's just commit the previous block if we find a new definition.
            # Wait, if current_block only has whitespace/jsdoc, we don't commit it yet.
            pass

    # Actually, a better way:
    # A block ends when a new definition starts, EXCEPT if the new definition is inside the block (indented)
    pass

# Let's do it simpler.
# Find the line numbers of all definitions.
defs = []
for i, line in enumerate(lines):
    if not line.startswith(' ') and not line.startswith('\t'):
        name = get_def_name(line)
        if name:
            # find jsdoc above it
            start_i = i
            for j in range(i-1, -1, -1):
                if lines[j].strip().startswith('//') or lines[j].strip().startswith('*') or lines[j].strip().startswith('/*') or lines[j].strip() == '':
                    start_i = j
                else:
                    break
            defs.append({'name': name, 'start': start_i, 'def_line': i})

# Now each block goes from its start_i to the next block's start_i
for idx, d in enumerate(defs):
    end_i = defs[idx+1]['start'] if idx + 1 < len(defs) else len(lines)
    d['content'] = "".join(lines[d['start']:end_i]).strip()

# Now we have all blocks mapped by name
blocks = {d['name']: d['content'] for d in defs}

files = {
    'utils.ts': [
        'escapeRegExp',
        'generateSearchVariations',
        'searchRobust',
        'searchWithVariations',
        'findParagraphIndexByText',
        'stripFormatting',
        'isNormalizedMatch'
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

# Create files
for file_name, func_names in files.items():
    file_path = os.path.join(out_dir, file_name)
    with open(file_path, 'w', encoding='utf-8') as f:
        # We will let typescript figure out basic imports, but let's add cross-file imports
        if file_name != 'utils.ts':
            f.write('import { searchRobust, searchWithVariations, findParagraphIndexByText, stripFormatting, isNormalizedMatch, escapeRegExp, generateSearchVariations } from "./utils";\n')
        if file_name == 'formatting.ts':
            f.write('import { FormattingOperation } from "../types";\n')
        if file_name == 'replace.ts':
            f.write('import { SIMULATED_DELETION_PREFIX, SIMULATED_DELETION_SUFFIX, SIMULATED_INSERTION_PREFIX, SIMULATED_INSERTION_SUFFIX } from "./tracking";\n')
        if file_name == 'tracking.ts':
            f.write('import { replaceTextInParagraph } from "./replace";\n')
        if file_name == 'comments.ts':
            # no extra deps
            pass
            
        f.write('\n')
        
        for name in func_names:
            if name in blocks:
                block_content = blocks[name]
                # inject export if missing
                if not block_content.strip().startswith('export '):
                    block_content = re.sub(r'^(/\*\*[\s\S]*?\*/\s*)?(async\s+)?(function|const|interface|type)', r'\1export \2\3', block_content)
                f.write(block_content + '\n\n')
            else:
                print(f"MISSING: {name}")

# Create index.ts
with open(os.path.join(out_dir, 'index.ts'), 'w', encoding='utf-8') as f:
    for file_name in files.keys():
        if file_name != 'index.ts':
            module_name = file_name.replace('.ts', '')
            f.write(f'export * from "./{module_name}";\n')

print("Done generating files!")
