export async function searchAndSelect(text: string, occurrence: number): Promise<Word.Range | null> {
  try {
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

      if (searchResults.items.length > occurrence) {
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
      const ranges = body.getRanges();
      context.load(ranges, 'items');
      await context.sync();

      for (const r of ranges.items) {
        r.font.highlightColor = null;
      }
      await context.sync();
    }).catch(() => {});
  } catch {
    // ignore
  }
}

export async function replaceText(text: string, replacement: string, occurrence: number = 0): Promise<boolean> {
  try {
    let success = false;
    await Word.run(async (context) => {
      const body = context.document.body;
      const searchResults = body.search(text, {
        matchCase: true,
        ignorePunct: false,
        ignoreSpace: false,
      });
      context.load(searchResults, 'items');
      await context.sync();

      if (searchResults.items.length > occurrence) {
        const target = searchResults.items[occurrence];
        target.insertText(replacement, Word.InsertLocation.replace);
        success = true;
        await context.sync();
      }
    }).catch(() => {});
    return success;
  } catch {
    return false;
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
          const authorItem = authorProp.items.getOrNullObject('Author');
          if (!authorItem.isNull) {
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
