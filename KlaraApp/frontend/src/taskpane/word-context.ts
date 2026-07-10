export async function searchAndSelect(
  text: string,
  occurrence: number
): Promise<Word.Range | null> {
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
      context.load(searchResults, "items");
      await context.sync();

      if (occurrence >= 0 && searchResults.items.length > occurrence) {
        range = searchResults.items[occurrence];

        // Workaround: Insert a temporary content control to force viewport update
        const tempControl = range.insertContentControl();
        tempControl.select();
        await context.sync();

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

                if (newRange.text === replacement) {
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

              if (newRange.text === replacement) {
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

            if (newRange.text === replacement) {
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

/**
 * Enhanced search function that tries multiple text variations
 */
async function searchWithVariations(
  searchScope: Word.Body | Word.Paragraph,
  text: string,
  occurrence: number = 0
): Promise<Word.Range | null> {
  const variations = generateSearchVariations(text);
  console.log(`🔍 Trying ${variations.length} search variations for "${text}"`);

  for (let i = 0; i < variations.length; i++) {
    const variation = variations[i];
    console.log(`🔍 Variation ${i + 1}/${variations.length}: "${variation}"`);

    try {
      // Try exact match first
      let searchResults = searchScope.search(variation, {
        matchCase: true,
        ignorePunct: false,
        ignoreSpace: false,
      });
      searchResults.context.load(searchResults, "items");
      await searchResults.context.sync();

      if (searchResults.items.length > occurrence) {
        console.log(`✅ Found with exact match: "${variation}"`);
        return searchResults.items[occurrence];
      }

      // Try case-insensitive
      searchResults = searchScope.search(variation, {
        matchCase: false,
        ignorePunct: true,
        ignoreSpace: true,
      });
      searchResults.context.load(searchResults, "items");
      await searchResults.context.sync();

      if (searchResults.items.length > occurrence) {
        console.log(`✅ Found with relaxed match: "${variation}"`);
        return searchResults.items[occurrence];
      }

      // Try wildcard for special characters
      if (/[^\w\s]/.test(variation)) {
        const wildcard = variation.replace(/[^\w\s]/g, "?");
        searchResults = searchScope.search(wildcard, { matchWildcards: true });
        searchResults.context.load(searchResults, "items");
        await searchResults.context.sync();

        if (searchResults.items.length > occurrence) {
          console.log(`✅ Found with wildcard: "${wildcard}"`);
          return searchResults.items[occurrence];
        }
      }
    } catch (e) {
      console.warn(`⚠️ Search failed for variation "${variation}":`, e);
      continue;
    }
  }

  console.log(`❌ All search variations failed for "${text}"`);
  return null;
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

          if (newRange.text === replacement) {
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

export async function getDocumentMetadata(): Promise<{ title: string; author: string }> {
  try {
    let title = "";
    let author = "";
    await Word.run(async (context) => {
      const props = context.document.properties;
      context.load(props, "title");
      await context.sync();
      title = props.title || "";
    }).catch(() => {});

    try {
      await Word.run(async (context) => {
        const authorProp = (context.document as any).getCustomProperties?.() || null;
        if (authorProp) {
          context.load(authorProp, "items");
          await context.sync();
          const authorItem = authorProp.tryGetByKey("Author");
          if (authorItem && !authorItem.isNull) {
            author = authorItem.value?.toString() || "";
          }
        }
      }).catch(() => {});
    } catch {
      // ignore custom property errors
    }

    return { title, author };
  } catch {
    return { title: "", author: "" };
  }
}

export async function getDocumentSelection(): Promise<string> {
  try {
    let text = "";
    await Word.run(async (context) => {
      const selection = context.document.getSelection();
      context.load(selection, "text");
      await context.sync();
      text = selection.text || "";
    }).catch(() => {});
    return text;
  } catch {
    return "";
  }
}

/**
 * Test if Word API is available and working properly
 * Returns true if Word API is responsive, false otherwise
 */
/**
 * Create an inline comment in Word authored by Klara
 * @param text The text to add a comment on
 * @param comment The comment text content
 * @param findingId Optional finding ID to include in the comment
 */
export async function createKlaraComment(
  text: string,
  commentText: string,
  findingId?: string
): Promise<{ success: boolean; message: string }> {
  try {
    let message = "";
    let success = false;

    await Word.run(async (context) => {
      try {
        const body = context.document.body;

        // Search for the text to comment on
        const target = await searchWithVariations(body, text, 0);

        if (target) {
          // Create a comment on the found text range
          target.insertComment(commentText);
          await context.sync();

          success = true;
          message = `Comment added by Klara AI ${findingId ? `(Finding ID: ${findingId})` : ""}`;
        } else {
          message = `Text "${text}" not found in document`;
        }
      } catch (wordError) {
        console.error("Error inside Word.run for comment creation:", wordError);
        message = `Word API error: ${wordError.message}`;
      }
    });

    return {
      success,
      message,
    };
  } catch (e: any) {
    console.error("Failed to create Klara comment:", e);
    return {
      success: false,
      message: `Failed to create comment: ${e.message || "Unknown error"}`,
    };
  }
}

/**
 * Create an inline comment in Word authored by Klara at a specific paragraph
 * @param text The text to add a comment on
 * @param comment The comment text content
 * @param paragraphIndex The paragraph index to search in
 * @param findingId Optional finding ID to include in the comment
 */
export async function createKlaraCommentInParagraph(
  text: string,
  commentText: string,
  paragraphIndex: number,
  findingId?: string
): Promise<{ success: boolean; message: string }> {
  try {
    let message = "";
    let success = false;

    await Word.run(async (context) => {
      try {
        const paragraphs = context.document.body.paragraphs;
        paragraphs.load("items");
        await context.sync();

        if (paragraphIndex >= 0 && paragraphIndex < paragraphs.items.length) {
          const paragraph = paragraphs.items[paragraphIndex];

          // Search for the text in the specific paragraph
          const target = await searchWithVariations(paragraph, text, 0);

          if (target) {
            // Create a comment on the found text range
            target.insertComment(commentText);
            await context.sync();

            success = true;
            message = `Comment added by Klara AI in paragraph ${paragraphIndex} ${findingId ? `(Finding ID: ${findingId})` : ""}`;
          } else {
            message = `Text "${text}" not found in paragraph ${paragraphIndex}`;
          }
        } else {
          message = `Paragraph index ${paragraphIndex} out of range`;
        }
      } catch (wordError) {
        console.error("Error inside Word.run for comment creation:", wordError);
        message = `Word API error: ${wordError.message}`;
      }
    });

    return {
      success,
      message,
    };
  } catch (e: any) {
    console.error("Failed to create Klara comment in paragraph:", e);
    return {
      success: false,
      message: `Failed to create comment: ${e.message || "Unknown error"}`,
    };
  }
}

/**
 * Create a comment at a specific paragraph index (no text search needed)
 * @param paragraphIndex The paragraph index to add the comment on
 * @param commentText The comment text content
 * @param findingId Optional finding ID to include in the comment
 */
export async function createKlaraCommentAtParagraph(
  paragraphIndex: number,
  commentText: string,
  findingId?: string
): Promise<{ success: boolean; message: string }> {
  try {
    let message = "";
    let success = false;

    await Word.run(async (context) => {
      try {
        const paragraphs = context.document.body.paragraphs;
        paragraphs.load("items");
        await context.sync();

        if (paragraphIndex >= 0 && paragraphIndex < paragraphs.items.length) {
          const paragraph = paragraphs.items[paragraphIndex];
          const range = paragraph.getRange();
          range.insertComment(commentText);
          await context.sync();

          success = true;
          message = `Comment added by Klara AI at paragraph ${paragraphIndex} ${findingId ? `(Finding ID: ${findingId})` : ""}`;
        } else {
          message = `Paragraph index ${paragraphIndex} out of range`;
        }
      } catch (wordError) {
        console.error("Error inside Word.run for comment creation at paragraph:", wordError);
        message = `Word API error: ${wordError.message}`;
      }
    });

    return {
      success,
      message,
    };
  } catch (e: any) {
    console.error("Failed to create Klara comment at paragraph:", e);
    return {
      success: false,
      message: `Failed to create comment: ${e.message || "Unknown error"}`,
    };
  }
}

/**
 * Test if Word API is available and working properly
 * Returns true if Word API is responsive, false otherwise
 */
export async function testWordApiAvailability(): Promise<{
  available: boolean;
  error?: string;
  documentInfo?: any;
}> {
  try {
    let documentInfo: any = {};

    await Word.run(async (context) => {
      try {
        const doc = context.document;
        const body = doc.body;

        // Test basic document access
        context.load(body, "text");
        await context.sync();

        documentInfo = {
          hasContent: body.text && body.text.length > 0,
          contentLength: body.text ? body.text.length : 0,
          firstChars: body.text ? body.text.substring(0, 50) : "",
        };

        console.log("Word API test successful:", documentInfo);
        return { available: true, documentInfo };
      } catch (innerError) {
        console.error("Word API inner test failed:", innerError);
        throw innerError;
      }
    });

    return { available: true, documentInfo };
  } catch (e: any) {
    console.error("Word API availability test failed:", e);
    return {
      available: false,
      error: e.message || "Word API not available or not responding",
    };
  }
}

/**
 * Generate multiple search variations for special characters
 * This helps handle different Unicode representations and encoding issues
 */
function generateSearchVariations(text: string): string[] {
  const variations: string[] = [text];

  // Normalize Unicode to NFC form (canonical decomposition + composition)
  try {
    variations.push(text.normalize("NFC"));
  } catch {
    // ignore normalization errors
  }

  // Replace non-breaking spaces with regular spaces
  const noNBSP = text.replace(/\u00A0/g, " ");
  if (noNBSP !== text) {
    variations.push(noNBSP);
    // Also normalize the no-NBSP version
    try {
      variations.push(noNBSP.normalize("NFC"));
    } catch {
      // ignore
    }
  }

  // Remove zero-width spaces
  const noZWSP = text.replace(/\u200B/g, "");
  if (noZWSP !== text) {
    variations.push(noZWSP);
  }

  // Handle different dash types
  const dashMap: Record<string, string> = {
    "\u2013": "-", // en-dash → hyphen
    "\u2014": "--", // em-dash → double hyphen
    "\u2012": "-", // figure dash → hyphen
  };
  let normalizedDashes = text;
  for (const [dash, replacement] of Object.entries(dashMap)) {
    normalizedDashes = normalizedDashes.replace(new RegExp(dash, "g"), replacement);
  }
  if (normalizedDashes !== text) {
    variations.push(normalizedDashes);
  }

  // Handle different apostrophe/quote types
  const apostropheMap: Record<string, string> = {
    "\u2018": "'", // left single quote
    "\u2019": "'", // right single quote
    "\u02BC": "'", // modifier letter apostrophe
    "\u2032": "'", // prime
    "\u201A": "'", // single low-9 quotation mark
    "\u201B": "'", // single high-reversed-9 quotation mark
  };
  let normalizedApostrophes = text;
  for (const [apostrophe, replacement] of Object.entries(apostropheMap)) {
    normalizedApostrophes = normalizedApostrophes.replace(new RegExp(apostrophe, "g"), replacement);
  }
  if (normalizedApostrophes !== text) {
    variations.push(normalizedApostrophes);
  }

  // Handle common special characters that might have different representations
  const specialChars: Record<string, string[]> = {
    "§": ["§", "§", "\\S+", "\\section"],
    "©": ["©", "©", "(c)"],
    "®": ["®", "®", "(r)"],
    "™": ["™", "™", "(tm)"],
    "—": ["—", "—", "--"],
    "–": ["–", "–", "-"],
    '"': ['"', "\u201C", "\u201D", "\u201E", "\u201F", "\u201A", "\u201B"],
    "'": ["'", "\u2018", "\u2019", "\u201A", "\u201B", "\u02BC", "\u2032"],
    "…": ["…", "…", "..."],
    "°": ["°", "°", "{degree}"],
    "±": ["±", "±", "+/-"],
    "×": ["×", "×", "x"],
    "÷": ["÷", "÷", "/"],
  };

  for (const [char, alternatives] of Object.entries(specialChars)) {
    if (text.includes(char)) {
      for (const alt of alternatives) {
        if (alt !== char) {
          variations.push(text.replace(char, alt));
        }
      }
    }
  }

  // Add wildcard version (replace special chars with ?)
  const wildcardVersion = text.replace(/[^\w\s]/g, "?");
  if (wildcardVersion !== text) {
    variations.push(wildcardVersion);
  }

  return Array.from(new Set(variations));
}

/**
 * Result type for formatting operations
 */
export interface FormattingResult {
  success: boolean;
  applied: boolean;
  message: string;
  paragraphIndex?: number;
}

/**
 * Apply formatting fix to a paragraph
 * @param paragraphIndex The index of the paragraph to format
 * @param operation The formatting operation to apply
 */
export async function applyParagraphFormatting(
  paragraphIndex: number,
  operation: any
): Promise<FormattingResult> {
  try {
    let message = "";
    let applied = false;
    let actualParagraphIndex = paragraphIndex;

    await Word.run(async (context) => {
      try {
        const paragraphs = context.document.body.paragraphs;
        paragraphs.load("items");
        await context.sync();

        if (paragraphIndex >= 0 && paragraphIndex < paragraphs.items.length) {
          const paragraph = paragraphs.items[paragraphIndex] as any;

          // Apply the formatting operation based on type
          switch (operation.type) {
            case "keep_with_next":
              paragraph.keepWithNext = operation.value;
              message = operation.value
                ? 'Enabled "Keep with next" to prevent orphan headings'
                : 'Disabled "Keep with next"';
              applied = true;
              break;

            case "page_break_before":
              paragraph.pageBreakBefore = operation.value;
              message = operation.value
                ? "Enabled page break before"
                : "Disabled page break before";
              applied = true;
              break;

            case "widow_orphan_control":
              paragraph.widowControl = operation.value;
              message = operation.value
                ? "Enabled widow/orphan control"
                : "Disabled widow/orphan control";
              applied = true;
              break;

            case "line_spacing":
              if (typeof operation.value === "number") {
                paragraph.lineSpacing = operation.value;
                message = `Set line spacing to ${operation.value}`;
                applied = true;
              } else {
                message = "Invalid line spacing value";
              }
              break;

            case "alignment":
              // Map string alignment values to Word.Alignment enum
              const alignmentMap: Record<string, Word.Alignment> = {
                left: Word.Alignment.left,
                right: Word.Alignment.right,
                center: Word.Alignment.centered,
                justified: Word.Alignment.justified,
                distributed: Word.Alignment.left, // fallback for distributed
              };

              if (typeof operation.value === "string" && alignmentMap[operation.value]) {
                paragraph.alignment = alignmentMap[operation.value];
                message = `Set alignment to ${operation.value}`;
                applied = true;
              } else {
                message = `Invalid alignment value: ${operation.value}`;
              }
              break;

            default:
              message = `Unknown formatting operation type: ${operation.type}`;
              applied = false;
          }

          await context.sync();
        } else {
          message = `Paragraph index ${paragraphIndex} out of range (0-${paragraphs.items.length - 1})`;
          applied = false;
        }
      } catch (wordError) {
        console.error("Error inside Word.run for formatting:", wordError);
        message = `Word API error: ${wordError.message}`;
        applied = false;
      }
    });

    return {
      success: true,
      applied,
      message,
      paragraphIndex: actualParagraphIndex,
    };
  } catch (e: any) {
    console.error("Failed to apply paragraph formatting:", e);
    return {
      success: false,
      applied: false,
      message: `Failed to apply formatting: ${e.message || "Unknown error"}`,
    };
  }
}

/**
 * Search for and apply formatting to a paragraph containing specific text
 * @param searchText The text to search for
 * @param operation The formatting operation to apply
 */
export async function searchAndApplyFormatting(
  searchText: string,
  operation: any
): Promise<FormattingResult> {
  try {
    let message = "";
    let applied = false;
    let foundParagraphIndex: number | undefined = undefined;

    await Word.run(async (context) => {
      try {
        const body = context.document.body;
        const paragraphs = body.paragraphs;
        paragraphs.load("items");
        await context.sync();

        // Search for the paragraph containing the text
        for (let i = 0; i < paragraphs.items.length; i++) {
          const paragraph = paragraphs.items[i];
          paragraph.load("text");
          await context.sync();

          if (paragraph.text && paragraph.text.includes(searchText)) {
            foundParagraphIndex = i;
            const paragraphAny = paragraph as any;

            // Apply the formatting operation based on type
            switch (operation.type) {
              case "keep_with_next":
                paragraphAny.keepWithNext = operation.value;
                message = operation.value
                  ? `Enabled "Keep with next" for paragraph containing "${searchText}"`
                  : `Disabled "Keep with next" for paragraph containing "${searchText}"`;
                applied = true;
                break;

              case "page_break_before":
                paragraphAny.pageBreakBefore = operation.value;
                message = operation.value
                  ? `Enabled page break before for paragraph containing "${searchText}"`
                  : `Disabled page break before for paragraph containing "${searchText}"`;
                applied = true;
                break;

              case "widow_orphan_control":
                paragraphAny.widowControl = operation.value;
                message = operation.value
                  ? `Enabled widow/orphan control for paragraph containing "${searchText}"`
                  : `Disabled widow/orphan control for paragraph containing "${searchText}"`;
                applied = true;
                break;

              case "line_spacing":
                if (typeof operation.value === "number") {
                  paragraphAny.lineSpacing = operation.value;
                  message = `Set line spacing to ${operation.value} for paragraph containing "${searchText}"`;
                  applied = true;
                } else {
                  message = "Invalid line spacing value";
                }
                break;

              case "alignment":
                const alignmentMap: Record<string, Word.Alignment> = {
                  left: Word.Alignment.left,
                  right: Word.Alignment.right,
                  center: Word.Alignment.centered,
                  justified: Word.Alignment.justified,
                  distributed: Word.Alignment.left, // fallback for distributed
                };

                if (typeof operation.value === "string" && alignmentMap[operation.value]) {
                  paragraphAny.alignment = alignmentMap[operation.value];
                  message = `Set alignment to ${operation.value} for paragraph containing "${searchText}"`;
                  applied = true;
                } else {
                  message = `Invalid alignment value: ${operation.value}`;
                }
                break;

              default:
                message = `Unknown formatting operation type: ${operation.type}`;
                applied = false;
            }

            await context.sync();
            break; // Found and processed, exit loop
          }
        }

        if (!foundParagraphIndex) {
          message = `Could not find paragraph containing "${searchText}"`;
          applied = false;
        }
      } catch (wordError) {
        console.error("Error inside Word.run for search and format:", wordError);
        message = `Word API error: ${wordError.message}`;
        applied = false;
      }
    });

    return {
      success: true,
      applied,
      message,
      paragraphIndex: foundParagraphIndex,
    };
  } catch (e: any) {
    console.error("Failed to search and apply formatting:", e);
    return {
      success: false,
      applied: false,
      message: `Failed to apply formatting: ${e.message || "Unknown error"}`,
    };
  }
}

/**
 * Creates a simulated tracked change for a text replacement
 */
export async function createSimulatedTrackedChange(
  text: string,
  replacementText: string,
  commentText: string,
  findingId: string
): Promise<{ success: boolean; message: string }> {
  try {
    let message = "";
    let success = false;

    await Word.run(async (context) => {
      try {
        const body = context.document.body;
        const target = await searchWithVariations(body, text, 0);

        if (target) {
          const originalText = target.text;
          const suggestedReplacement = " " + replacementText;

          // Format original text
          target.font.strikeThrough = true;
          target.font.color = "#FF0000";

          // Insert replacement text
          const replacementRange = target.insertText(suggestedReplacement, Word.InsertLocation.after);
          
          // Format replacement text
          replacementRange.font.color = "#0000FF";
          replacementRange.font.underline = Word.UnderlineType.single;

          // Wrap in a Content Control
          const fullRange = target.expandTo(replacementRange);
          const cc = fullRange.insertContentControl();
          cc.title = `Klara Suggestion: ${findingId}`;
          cc.tag = findingId;

          // Add a comment to the original selection
          target.insertComment(`[Klara Suggestion] Replace "${originalText}" with "${replacementText}"\n\n${commentText}`);
          
          await context.sync();
          success = true;
          message = `Simulated tracked change created for ${findingId}`;
        } else {
          message = `Text "${text}" not found in document`;
        }
      } catch (wordError) {
        console.error("Error creating simulated track change:", wordError);
        message = `Word API error: ${wordError.message}`;
      }
    });

    return { success, message };
  } catch (e: any) {
    console.error("Failed to create simulated track change:", e);
    return { success: false, message: e.message || "Unknown error" };
  }
}

/**
 * Creates a simulated tracked change for a text replacement in a specific paragraph
 */
export async function createSimulatedTrackedChangeInParagraph(
  text: string,
  replacementText: string,
  commentText: string,
  paragraphIndex: number,
  findingId: string
): Promise<{ success: boolean; message: string }> {
  try {
    let message = "";
    let success = false;

    await Word.run(async (context) => {
      try {
        const paragraphs = context.document.body.paragraphs;
        paragraphs.load("items");
        await context.sync();

        if (paragraphIndex >= 0 && paragraphIndex < paragraphs.items.length) {
          const paragraph = paragraphs.items[paragraphIndex];
          const target = await searchWithVariations(paragraph, text, 0);

          if (target) {
            const originalText = target.text;
            const suggestedReplacement = " " + replacementText;

            target.font.strikeThrough = true;
            target.font.color = "#FF0000";

            const replacementRange = target.insertText(suggestedReplacement, Word.InsertLocation.after);
            replacementRange.font.color = "#0000FF";
            replacementRange.font.underline = Word.UnderlineType.single;

            const fullRange = target.expandTo(replacementRange);
            const cc = fullRange.insertContentControl();
            cc.title = `Klara Suggestion: ${findingId}`;
            cc.tag = findingId;

            target.insertComment(`[Klara Suggestion] Replace "${originalText}" with "${replacementText}"\n\n${commentText}`);
            
            await context.sync();
            success = true;
            message = `Simulated tracked change created in paragraph ${paragraphIndex}`;
          } else {
            message = `Text "${text}" not found in paragraph ${paragraphIndex}`;
          }
        } else {
          message = `Paragraph index ${paragraphIndex} out of range`;
        }
      } catch (wordError) {
        console.error("Error creating simulated track change:", wordError);
        message = `Word API error: ${wordError.message}`;
      }
    });

    return { success, message };
  } catch (e: any) {
    console.error("Failed to create simulated track change:", e);
    return { success: false, message: e.message || "Unknown error" };
  }
}

/**
 * Accepts a simulated tracked change by applying the replacement text and removing the wrapper
 */
export async function acceptSimulatedTrackedChange(
  findingId: string,
  replacementText: string
): Promise<{ success: boolean; message: string }> {
  try {
    let message = "";
    let success = false;

    await Word.run(async (context) => {
      const controls = context.document.contentControls.getByTag(findingId);
      controls.load("items");
      await context.sync();

      if (controls.items.length > 0) {
        const cc = controls.items[0];
        cc.clear();
        cc.insertText(replacementText, "Replace");
        cc.delete(true); // Keep the content
        await context.sync();
        success = true;
        message = "Successfully accepted simulated tracked change.";
      } else {
        message = "Simulated tracked change not found in document.";
      }
    });

    return { success, message };
  } catch (e: any) {
    console.error("Failed to accept simulated track change:", e);
    return { success: false, message: e.message || "Unknown error" };
  }
}

/**
 * Rejects a simulated tracked change by reverting to the original text and removing the wrapper
 */
export async function rejectSimulatedTrackedChange(
  findingId: string,
  originalText: string
): Promise<{ success: boolean; message: string }> {
  try {
    let message = "";
    let success = false;

    await Word.run(async (context) => {
      const controls = context.document.contentControls.getByTag(findingId);
      controls.load("items");
      await context.sync();

      if (controls.items.length > 0) {
        const cc = controls.items[0];
        cc.clear();
        cc.insertText(originalText, "Replace");
        cc.delete(true); // Keep the content
        await context.sync();
        success = true;
        message = "Successfully rejected simulated tracked change.";
      } else {
        message = "Simulated tracked change not found in document.";
      }
    });

    return { success, message };
  } catch (e: any) {
    console.error("Failed to reject simulated track change:", e);
    return { success: false, message: e.message || "Unknown error" };
  }
}

/**
 * Undoes a simulated tracked change completely, reverting to the original text and removing the wrapper
 */
export async function undoSimulatedTrackedChange(
  findingId: string,
  originalText: string
): Promise<{ success: boolean; message: string }> {
  return rejectSimulatedTrackedChange(findingId, originalText); // Functionally identical
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

export async function getActiveDocumentData(): Promise<{
  title: string;
  author: string;
  url?: string;
  blob?: Blob;
}> {
  let title = "Document.docx";
  let author = "Unknown";
  let url = Office.context.document.url;

  try {
    await Word.run(async (context) => {
      const props = context.document.properties;
      context.load(props, "title, author");
      await context.sync();
      if (props.title) title = props.title;
      if ((props as any).author) author = (props as any).author;
    });
  } catch (e) {
    // ignore
  }

  // NOTE: Even when the document is cloud-hosted (url is an https:// SharePoint/OneDrive link)
  // we still extract the binary via getFileAsync, because the backend does not yet have a
  // Graph-URL ingestion endpoint. Once that endpoint is built, we can return { title, author, url }
  // here for the faster server-side pull path.

  // Fallback to getFileAsync for local/unsaved docs
  return new Promise((resolve, reject) => {
    Office.context.document.getFileAsync(
      Office.FileType.Compressed,
      { sliceSize: 65536 },
      (result) => {
        if (result.status === Office.AsyncResultStatus.Succeeded) {
          const file = result.value;
          const sliceCount = file.sliceCount;
          const slicesReceived: ArrayBuffer[] = [];
          let slicesRead = 0;

          const getSlice = (sliceIndex: number) => {
            file.getSliceAsync(sliceIndex, (sliceResult) => {
              if (sliceResult.status === Office.AsyncResultStatus.Succeeded) {
                // Ensure the slice data is Uint8Array
                const sliceData = sliceResult.value.data;
                let typedArray: Uint8Array;
                if (sliceData instanceof ArrayBuffer) {
                  typedArray = new Uint8Array(sliceData);
                } else if (sliceData instanceof Uint8Array) {
                  typedArray = sliceData;
                } else {
                  typedArray = new Uint8Array(sliceData as any);
                }
                slicesReceived[sliceIndex] = typedArray.buffer as ArrayBuffer;
                slicesRead++;

                if (slicesRead === sliceCount) {
                  file.closeAsync();
                  const blob = new Blob(slicesReceived, {
                    type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                  });
                  resolve({ title, author, blob });
                } else {
                  getSlice(sliceIndex + 1);
                }
              } else {
                file.closeAsync();
                reject(new Error(sliceResult.error.message));
              }
            });
          };

          if (sliceCount > 0) {
            getSlice(0);
          } else {
            file.closeAsync();
            resolve({ title, author, blob: new Blob() });
          }
        } else {
          reject(new Error(result.error.message));
        }
      }
    );
  });
}
