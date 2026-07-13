import {
  searchRobust,
  searchWithVariations,
  isNormalizedMatch,
  generateSearchVariations,
} from "./utils";

export async function searchAndSelect(
  text: string,
  occurrence: number
): Promise<{ range: Word.Range | null; error?: string }> {
  try {
    if (occurrence < 0) return { range: null };
    let finalRange: Word.Range | null = null;
    let errorMessage: string | undefined;

    await Word.run(async (context) => {
      const body = context.document.body;
      let target = await searchRobust(body, text, occurrence, context);

      if (!target && context.document.body.footnotes) {
        const footnotes = context.document.body.footnotes;
        footnotes.load("items");
        await context.sync();
        for (let i = 0; i < footnotes.items.length; i++) {
          const fnTarget = await searchRobust(footnotes.items[i].body, text, 0, context);
          if (fnTarget) {
            target = fnTarget;
            break;
          }
        }
      }

      if (target) {
        try {
          // Workaround: Force a selection change to ensure Word updates the viewport and regains focus,
          // avoiding the "deselect" bug when reclicking the same card.
          const startRange = target.getRange("Start");
          startRange.select();
          await context.sync();

          target.select();
          await context.sync();
          finalRange = target;
        } catch (selectionError: any) {
          console.warn(
            "Precise selection failed, attempting safe paragraph fallback:",
            selectionError
          );
          errorMessage = selectionError.message || "Unknown selection error";

          try {
            // Re-run Word.run because context might be poisoned by the error
            // Actually, we can't easily re-run Word.run for target inside this block without losing 'target'.
            // Wait, in Office.js, if a batch fails, the context is ruined.
          } catch (e) {}
        }
      }
    });

    // If the batch failed, we do a completely separate safe search outside the ruined context
    if (errorMessage && !finalRange) {
      await Word.run(async (safeContext) => {
        const body = safeContext.document.body;
        let target = await searchRobust(body, text, occurrence, safeContext);
        if (target) {
          const paragraphs = target.paragraphs;
          paragraphs.load("items");
          await safeContext.sync();
          if (paragraphs.items.length > 0) {
            const startPara = paragraphs.items[0];
            const endPara = paragraphs.items[paragraphs.items.length - 1];
            const safeRange = startPara.getRange("Start").expandTo(endPara.getRange("End"));

            const startSafeRange = safeRange.getRange("Start");
            startSafeRange.select();
            await safeContext.sync();

            safeRange.select();
            await safeContext.sync();
            finalRange = safeRange;
          }
        }
      });
    }

    return { range: finalRange, error: errorMessage };
  } catch (error: any) {
    console.error("Error in searchAndSelect:", error);
    return { range: null, error: error.message };
  }
}

export async function selectParagraph(index: number, color?: string): Promise<Word.Range | null> {
  try {
    let range: Word.Range | null = null;
    await Word.run(async (context) => {
      const paragraphs = context.document.body.paragraphs;
      paragraphs.load("items");
      await context.sync();

      if (index >= 0 && index < paragraphs.items.length) {
        const paragraph = paragraphs.items[index];
        range = paragraph.getRange();

        // Workaround: Insert a temporary content control to force viewport update
        const tempControl = range.insertContentControl();
        tempControl.select();
        await context.sync();

        // Apply highlight color to the paragraph range
        if (color) {
          range.font.highlightColor = color;
          await context.sync();
        }

        // Remove the temporary content control while keeping the text
        tempControl.delete(true);
        await context.sync();

        // Re-select the range to ensure it's selected after removing the control
        range.select();
        await context.sync();
      }
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
      const range = body.getRange();
      range.font.highlightColor = null;
      await context.sync();
    }).catch(() => {});
  } catch {
    // ignore
  }
}
