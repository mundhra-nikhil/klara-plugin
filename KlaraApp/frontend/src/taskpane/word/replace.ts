import {
  searchRobust,
  searchWithVariations,
  isNormalizedMatch,
  generateSearchVariations,
} from "./utils";

/**
 * Result type for text replacement operations
 */
export interface TextReplacementResult {
  success: boolean;
  applied: boolean;
  foundInDocument: boolean;
  actualParagraphIndex?: number;
  message: string;
}

export async function replaceTextInParagraph(
  text: string,
  replacement: string,
  paragraphIndex: number
): Promise<TextReplacementResult> {
  // Strip common automatic list/bullet prefixes if they exist on both strings.
  // Word's API hides automatic bullets from paragraph.text, but the AI often includes them.
  // If we don't strip them, the search fails, or we end up duplicating the bullet in the document.
  const prefixMatch = text.match(/^(\s*(\d+[.)\]]|[a-zA-Z]+[.)\]]|\([a-zA-Z0-9]+\)|[-•*])\s+)+/);
  if (prefixMatch) {
    const prefix = prefixMatch[0];
    if (replacement.startsWith(prefix)) {
      text = text.substring(prefix.length);
      replacement = replacement.substring(prefix.length);
      console.log(`ℹ️ Stripped common list prefix "${prefix}" from search and replacement text`);
    }
  }

  let applied = false;
  let foundInDocument = false;
  let actualParagraphIndex: number | undefined = undefined;
  let message = "";

  try {
    await Word.run(async (context) => {
      try {
        const paragraphs = context.document.body.paragraphs;
        paragraphs.load("items");
        await context.sync();

        console.log(
          `🔍 Searching for "${text}" in paragraph ${paragraphIndex} of ${paragraphs.items.length} total paragraphs`
        );

        if (paragraphIndex >= 0 && paragraphIndex < paragraphs.items.length) {
          const paragraph = paragraphs.items[paragraphIndex];

          // First, let's see what's actually in the paragraph for debugging
          paragraph.load("text");
          await context.sync();
          const paragraphText = paragraph.text;
          console.log(`📋 Paragraph ${paragraphIndex} content: "${paragraphText.trim()}"`);
          console.log(`📋 Looking for: "${text}"`);
          console.log(`📋 Contains search text? ${paragraphText.includes(text)}`);

          // Check if the text is actually in this paragraph
          if (!paragraphText.includes(text)) {
            console.warn(`⚠️ WARNING: Text "${text}" not found in paragraph ${paragraphIndex}`);
            console.log(`🔍 Starting comprehensive document search to find the actual location...`);

            // Search the entire document to find where the text actually is
            const body = context.document.body;
            const allParagraphs = body.paragraphs;
            context.load(allParagraphs, "items/text");
            await context.sync();

            let foundIndex = -1;
            let foundContent = "";

            for (let i = 0; i < allParagraphs.items.length; i++) {
              const p = allParagraphs.items[i];

              if (p.text && p.text.includes(text)) {
                foundIndex = i;
                foundContent = p.text;
                foundInDocument = true;
                actualParagraphIndex = i;
                console.log(
                  `🎯 Found text "${text}" in actual paragraph ${i}: "${foundContent.trim()}"`
                );
                break;
              }
            }

            if (foundIndex !== -1) {
              console.log(
                `✅ Found text in paragraph ${foundIndex}, proceeding with replacement there`
              );

              // Use the correct paragraph
              const correctParagraph = allParagraphs.items[foundIndex];
              const target = await searchWithVariations(correctParagraph, text, 0);

              if (target) {
                const originalText = target.text;
                console.log(`🎯 Found text to replace: "${originalText}"`);

                const newRange = target.insertText(replacement, "Replace");
                await context.sync();

                // Verify the change was applied
                newRange.load("text");
                await context.sync();

                if (isNormalizedMatch(newRange.text, replacement)) {
                  applied = true;
                  console.log(
                    `✅ Successfully replaced "${originalText}" with "${replacement}" in paragraph ${foundIndex}`
                  );
                  message = `Replaced in paragraph ${foundIndex} (original index ${paragraphIndex} was incorrect)`;
                } else {
                  console.warn(`⚠️ Replacement may not have worked as expected`);
                  applied = false;
                  message = `Replacement completed with unexpected result`;
                }
              }
            } else {
              console.log(`ℹ️ Could not find "${text}" in any paragraph of the document`);
              message = `Text "${text}" not found in document - likely stale suggestion`;
              foundInDocument = false;
            }

            // If still not found, try the enhanced search in the specified paragraph anyway
            if (!applied) {
              console.log(
                `🔄 Trying enhanced search in specified paragraph ${paragraphIndex} anyway...`
              );
            }
          } else {
            foundInDocument = true;
            actualParagraphIndex = paragraphIndex;
          }

          // Try the enhanced search with variations in the specified paragraph
          if (!applied && foundInDocument) {
            const target = await searchWithVariations(paragraph, text, 0);

            if (target) {
              const originalText = target.text;
              console.log(`🎯 Found text to replace: "${originalText}"`);

              const newRange = target.insertText(replacement, "Replace");
              await context.sync();

              // Verify the change was applied
              newRange.load("text");
              await context.sync();

              if (isNormalizedMatch(newRange.text, replacement)) {
                applied = true;
                console.log(
                  `✅ Successfully replaced "${originalText}" with "${replacement}" in paragraph ${paragraphIndex}`
                );
                message = `Successfully replaced text in paragraph ${paragraphIndex}`;
              } else {
                console.warn(
                  `⚠️ Replacement may not have worked as expected. Original: "${originalText}", Expected: "${replacement}", Got: "${newRange.text}"`
                );
                applied = false;
                message = `Replacement completed with unexpected result`;
              }
            } else {
              console.warn(
                `❌ No search results found for "${text}" in paragraph ${paragraphIndex}`
              );
              message = `Could not find exact match for "${text}" in paragraph ${paragraphIndex}`;
            }
          }
        } else {
          console.warn(
            `❌ Paragraph index ${paragraphIndex} out of range (0-${paragraphs.items.length - 1})`
          );
          message = `Paragraph index ${paragraphIndex} out of range`;
        }

        // Fallback: If paragraph index was misaligned (e.g. due to tables) and text wasn't found, search the whole body
        if (!applied && !foundInDocument) {
          console.log(`🔄 Paragraph search failed, trying whole body search...`);
          const body = context.document.body;
          const bodyTarget = await searchWithVariations(body, text, 0);

          if (bodyTarget) {
            const originalText = bodyTarget.text;
            console.log(`🎯 Body search found: "${originalText}"`);

            const newRange = bodyTarget.insertText(replacement, "Replace");
            await context.sync();

            // Verify the change was applied
            newRange.load("text");
            await context.sync();

            if (isNormalizedMatch(newRange.text, replacement)) {
              applied = true;
              foundInDocument = true;
              console.log(
                `✅ Successfully replaced "${originalText}" with "${replacement}" via body search`
              );
              message = `Found and replaced via document-wide search`;
            } else {
              console.warn(`⚠️ Body fallback replacement may not have worked as expected`);
              applied = false;
              message = `Replacement completed via body search`;
            }
          } else {
            console.log(`ℹ️ All search methods failed for "${text}" - suggestion is likely stale`);
            message = `Text "${text}" not found in document after exhaustive search`;
          }
        }
      } catch (wordError) {
        console.error("💥 Error inside Word.run context:", wordError);
        message = `Word API error: ${wordError.message}`;
      }
    });

    return {
      success: true, // Operation completed (even if text wasn't found)
      applied,
      foundInDocument,
      actualParagraphIndex,
      message,
    };
  } catch (e: any) {
    console.error("💥 replaceTextInParagraph error:", e);
    return {
      success: false,
      applied: false,
      foundInDocument: false,
      message: `Failed to complete replacement: ${e.message || "Unknown error"}`,
    };
  }
}

export async function replaceText(
  text: string,
  replacement: string,
  occurrence: number = 0
): Promise<TextReplacementResult> {
  let applied = false;
  let foundInDocument = false;
  let message = "";

  try {
    await Word.run(async (context) => {
      try {
        const body = context.document.body;
        console.log(`🔍 Searching for "${text}" in document body`);

        const target = await searchWithVariations(body, text, occurrence);

        if (target) {
          const originalText = target.text;
          console.log(`🎯 Found text: "${originalText}"`);

          const newRange = target.insertText(replacement, "Replace");
          await context.sync();

          // Verify the change was applied
          newRange.load("text");
          await context.sync();

          if (isNormalizedMatch(newRange.text, replacement)) {
            applied = true;
            foundInDocument = true;
            console.log(
              `✅ Successfully replaced "${originalText}" with "${replacement}" at occurrence ${occurrence}`
            );
            message = `Successfully replaced "${originalText}" with "${replacement}"`;
          } else {
            console.warn(
              `⚠️ Replacement may not have worked as expected. Original: "${originalText}", Expected: "${replacement}", Got: "${newRange.text}"`
            );
            applied = false;
            foundInDocument = true;
            message = `Replacement completed with unexpected result`;
          }
        } else {
          console.log(`ℹ️ Could not find "${text}" in document`);
          message = `Text "${text}" not found in document`;
        }
      } catch (wordError) {
        console.error("💥 Error inside Word.run context:", wordError);
        message = `Word API error: ${wordError.message}`;
      }
    });

    return {
      success: true,
      applied,
      foundInDocument,
      message,
    };
  } catch (e: any) {
    console.error("💥 replaceText error:", e);
    return {
      success: false,
      applied: false,
      foundInDocument: false,
      message: `Failed to complete replacement: ${e.message || "Unknown error"}`,
    };
  }
}

/**
 * Undoes a direct replacement
 */
export async function undoDirectReplacement(
  replacementText: string,
  originalText: string,
  paragraphIndex?: number
): Promise<{ success: boolean; message: string }> {
  try {
    let message = "";
    let success = false;

    await Word.run(async (context) => {
      let target: Word.Range | null = null;
      if (paragraphIndex !== undefined) {
        const paragraphs = context.document.body.paragraphs;
        paragraphs.load("items");
        await context.sync();
        if (paragraphIndex >= 0 && paragraphIndex < paragraphs.items.length) {
          target = await searchWithVariations(paragraphs.items[paragraphIndex], replacementText, 0);
        }
      }
      if (!target) {
        target = await searchWithVariations(context.document.body, replacementText, 0);
      }

      if (target) {
        target.insertText(originalText, "Replace");
        await context.sync();
        success = true;
        message = "Successfully reverted direct replacement.";
      } else {
        message = "Replacement text not found in document.";
      }
    });

    return { success, message };
  } catch (e: any) {
    console.error("Failed to undo direct replacement:", e);
    return { success: false, message: e.message || "Unknown error" };
  }
}
