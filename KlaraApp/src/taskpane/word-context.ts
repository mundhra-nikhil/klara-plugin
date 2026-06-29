export async function searchAndSelect(text: string, occurrence: number): Promise<Word.Range | null> {
  try {
    if (occurrence < 0) return null;
    let range: Word.Range | null = null;
    await Word.run(async (context) => {
      const body = context.document.body;
      const searchResults = body.search(text, {
        matchCase: true,
        ignorePunct: false,
        ignoreSpace: false,
      });
      context.load(searchResults, 'items');
      await context.sync();

      if (occurrence >= 0 && searchResults.items.length > occurrence) {
        range = searchResults.items[occurrence];
        range.select();
        await context.sync();
      }
    }).catch(() => {
      // Word API may not be available in all contexts
    });
    return range;
  } catch {
    return null;
  }
}

export async function selectParagraph(index: number, color?: string): Promise<Word.Range | null> {
  try {
    let range: Word.Range | null = null;
    await Word.run(async (context) => {
      const paragraphs = context.document.body.paragraphs;
      paragraphs.load('items');
      await context.sync();

      if (index >= 0 && index < paragraphs.items.length) {
        range = paragraphs.items[index].getRange();
        range.select();
        if (color) {
          range.font.highlightColor = color;
        }
        await context.sync();
      }
    }).catch(() => {});
    return range;
  } catch {
    return null;
  }
}

export async function highlightRange(range: Word.Range, color: string): Promise<void> {
  try {
    await Word.run(async (context) => {
      range.font.highlightColor = color;
      await context.sync();
    }).catch(() => {});
  } catch {
    // ignore
  }
}

export async function clearHighlights(): Promise<void> {
  try {
    await Word.run(async (context) => {
      const body = context.document.body;
      const range = body.getRange();
      range.font.highlightColor = null;
      await context.sync();
    }).catch(() => {});
  } catch {
    // ignore
  }
}

export async function replaceTextInParagraph(text: string, replacement: string, paragraphIndex: number): Promise<boolean> {
  try {
    let success = false;
    await Word.run(async (context) => {
      const paragraphs = context.document.body.paragraphs;
      paragraphs.load('items');
      await context.sync();

      if (paragraphIndex >= 0 && paragraphIndex < paragraphs.items.length) {
        const paragraph = paragraphs.items[paragraphIndex];
        let searchResults = paragraph.search(text, {
          matchCase: true,
          ignorePunct: false,
          ignoreSpace: false,
        });
        context.load(searchResults, 'items');
        await context.sync();

        if (searchResults.items.length === 0) {
          // Fallback search with more relaxed options if exact match fails
          searchResults = paragraph.search(text, {
            matchCase: false,
            ignorePunct: true,
            ignoreSpace: true,
          });
          context.load(searchResults, 'items');
          await context.sync();
        }

        if (searchResults.items.length === 0) {
          // Ultimate fallback for paragraph: wildcard search
          const wildcardText = text.replace(/[^\w]/g, '?');
          searchResults = paragraph.search(wildcardText, { matchWildcards: true });
          context.load(searchResults, 'items');
          await context.sync();
        }

        if (searchResults.items.length > 0) {
          const target = searchResults.items[0]; // Replace the first match IN THIS PARAGRAPH
          target.insertText(replacement, Word.InsertLocation.replace);
          await context.sync();
          success = true;
        }
      }

      // Fallback: If paragraph index was misaligned (e.g. due to tables) and text wasn't found, search the whole body
      if (!success) {
        const body = context.document.body;
        let bodyResults = body.search(text, { matchCase: true });
        context.load(bodyResults, 'items');
        await context.sync();
        
        if (bodyResults.items.length === 0) {
           bodyResults = body.search(text, { matchCase: false, ignorePunct: true, ignoreSpace: true });
           context.load(bodyResults, 'items');
           await context.sync();
        }
        
        if (bodyResults.items.length === 0) {
           // Ultimate fallback: Replace non-alphanumeric characters with '?' (matches any single character)
           // This handles curly vs straight quotes, non-breaking spaces, and hidden formatting.
           const wildcardText = text.replace(/[^\w]/g, '?');
           bodyResults = body.search(wildcardText, { matchWildcards: true });
           context.load(bodyResults, 'items');
           await context.sync();
        }

        if (bodyResults.items.length > 0) {
          bodyResults.items[0].insertText(replacement, Word.InsertLocation.replace);
          await context.sync();
          success = true;
        }
      }
    });
    if (!success) {
      throw new Error(`Could not find the exact text in paragraph ${paragraphIndex}. Please manually apply this fix.`);
    }
    return success;
  } catch (e: any) {
    console.error("replaceTextInParagraph error:", e);
    throw e;
  }
}

export async function replaceText(text: string, replacement: string, occurrence: number = 0): Promise<boolean> {
  try {
    let success = false;
    await Word.run(async (context) => {
      const body = context.document.body;
      let searchResults = body.search(text, {
        matchCase: true,
        ignorePunct: false,
        ignoreSpace: false,
      });
      context.load(searchResults, 'items');
      await context.sync();

      if (searchResults.items.length <= occurrence) {
        // Fallback search with more relaxed options
        searchResults = body.search(text, {
          matchCase: false,
          ignorePunct: true,
          ignoreSpace: true,
        });
        context.load(searchResults, 'items');
        await context.sync();
      }
      
      if (searchResults.items.length <= occurrence) {
        // Ultimate fallback: Replace non-alphanumeric characters with '?'
        const wildcardText = text.replace(/[^\w]/g, '?');
        searchResults = body.search(wildcardText, { matchWildcards: true });
        context.load(searchResults, 'items');
        await context.sync();
      }

      if (searchResults.items.length > occurrence) {
        const target = searchResults.items[occurrence];
        target.insertText(replacement, Word.InsertLocation.replace);
        await context.sync();
        success = true;
      }
    });
    if (!success) {
      throw new Error(`Could not find the exact text in the document. Please manually apply this fix.`);
    }
    return success;
  } catch (e: any) {
    console.error("replaceText error:", e);
    throw e;
  }
}

export async function getDocumentMetadata(): Promise<{ title: string; author: string }> {
  try {
    let title = '';
    let author = '';
    await Word.run(async (context) => {
      const props = context.document.properties;
      context.load(props, 'title');
      await context.sync();
      title = props.title || '';
    }).catch(() => {});

    try {
      await Word.run(async (context) => {
        const authorProp = (context.document as any).getCustomProperties?.() || null;
        if (authorProp) {
          context.load(authorProp, 'items');
          await context.sync();
          const authorItem = authorProp.tryGetByKey('Author');
          if (authorItem && !authorItem.isNull) {
            author = authorItem.value?.toString() || '';
          }
        }
      }).catch(() => {});
    } catch {
      // ignore custom property errors
    }

    return { title, author };
  } catch {
    return { title: '', author: '' };
  }
}

export async function getDocumentSelection(): Promise<string> {
  try {
    let text = '';
    await Word.run(async (context) => {
      const selection = context.document.getSelection();
      context.load(selection, 'text');
      await context.sync();
      text = selection.text || '';
    }).catch(() => {});
    return text;
  } catch {
    return '';
  }
}
