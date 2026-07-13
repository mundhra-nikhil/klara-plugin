import {
  searchRobust,
  searchWithVariations,
  isNormalizedMatch,
  generateSearchVariations,
} from "./utils";
import { FormattingOperation } from "../types";

/**
 * Result type for formatting operations
 */
export interface FormattingResult {
  success: boolean;
  applied: boolean;
  message: string;
  paragraphIndex?: number;
  foundInDocument?: boolean;
  previous_state?: any;
}

/**
 * Apply formatting fix to a paragraph
 * @param paragraphIndex The index of the paragraph to format
 * @param operation The formatting operation to apply
 */
export async function applyParagraphFormatting(
  paragraphIndex: number,
  operation: any,
  expectedText?: string
): Promise<FormattingResult> {
  try {
    let message = "";
    let applied = false;
    let actualParagraphIndex = paragraphIndex;
    let foundInDoc = true;
    let previousState: any = null;

    await Word.run(async (context) => {
      try {
        const paragraphs = context.document.body.paragraphs;
        paragraphs.load("items");
        await context.sync();

        let targetParagraph: Word.Paragraph | null = null;

        if (paragraphIndex >= 0 && paragraphIndex < paragraphs.items.length) {
          targetParagraph = paragraphs.items[paragraphIndex];

          if (expectedText) {
            const range = await searchWithVariations(targetParagraph, expectedText, 0);
            if (!range) {
              console.warn(
                `Text not found in expected paragraph ${paragraphIndex}. Searching document...`
              );
              const fallbackRange = await searchRobust(
                context.document.body,
                expectedText,
                0,
                context
              );
              if (fallbackRange) {
                targetParagraph = fallbackRange.paragraphs.getFirst();
                actualParagraphIndex = -1; // Unknown index after global search, but we have the target
              } else {
                targetParagraph = null; // Mark as not found
                foundInDoc = false;
              }
            }
          }
        } else if (expectedText) {
          const fallbackRange = await searchRobust(context.document.body, expectedText, 0, context);
          if (fallbackRange) {
            targetParagraph = fallbackRange.paragraphs.getFirst();
            actualParagraphIndex = -1;
          } else {
            foundInDoc = false;
          }
        } else {
          foundInDoc = false;
        }

        if (!targetParagraph) {
          message = `Paragraph index ${paragraphIndex} out of range and text not found`;
          applied = false;
        } else {
          const paragraphAny = targetParagraph as any;

          paragraphAny.load([
            "keepWithNext",
            "pageBreakBefore",
            "widowControl",
            "lineSpacing",
            "alignment",
          ]);
          paragraphAny.font.load(["name", "size"]);
          await context.sync();

          previousState = {
            type: "paragraph",
            paragraphIndex: actualParagraphIndex,
            keepWithNext: paragraphAny.keepWithNext,
            pageBreakBefore: paragraphAny.pageBreakBefore,
            widowControl: paragraphAny.widowControl,
            lineSpacing: paragraphAny.lineSpacing,
            alignment: paragraphAny.alignment,
            fontName: paragraphAny.font.name,
            fontSize: paragraphAny.font.size,
          };

          const operations = Array.isArray(operation) ? operation : [operation];

          for (const op of operations) {
            switch (op.type) {
              case "keep_with_next":
                const keepVal = op.value === true || String(op.value).toLowerCase() === "true";
                paragraphAny.keepWithNext = keepVal;
                message +=
                  (message ? " | " : "") +
                  (keepVal ? 'Enabled "Keep with next"' : 'Disabled "Keep with next"');
                applied = true;
                break;

              case "page_break_before":
                const pbVal = op.value === true || String(op.value).toLowerCase() === "true";
                paragraphAny.pageBreakBefore = pbVal;
                message +=
                  (message ? " | " : "") +
                  (pbVal ? "Enabled page break before" : "Disabled page break before");
                applied = true;
                break;

              case "widow_orphan_control":
                const woVal = op.value === true || String(op.value).toLowerCase() === "true";
                paragraphAny.widowControl = woVal;
                message +=
                  (message ? " | " : "") +
                  (woVal ? "Enabled widow/orphan control" : "Disabled widow/orphan control");
                applied = true;
                break;

              case "line_spacing":
                const parsedLineSpacing =
                  typeof op.value === "string"
                    ? parseInt(op.value.replace(/[^0-9.]/g, ""), 10)
                    : op.value;
                if (typeof parsedLineSpacing === "number" && !isNaN(parsedLineSpacing)) {
                  paragraphAny.lineSpacing = parsedLineSpacing;
                  message += (message ? " | " : "") + `Set line spacing to ${parsedLineSpacing}`;
                  applied = true;
                } else {
                  message += (message ? " | " : "") + `Invalid line spacing value: ${op.value}`;
                }
                break;

              case "alignment":
                // Map string alignment values to Word.Alignment enum
                const alignmentMap: Record<string, Word.Alignment> = {
                  left: Word.Alignment.left,
                  right: Word.Alignment.right,
                  center: Word.Alignment.centered,
                  justified: Word.Alignment.justified,
                  justify: Word.Alignment.justified,
                  "fully justified": Word.Alignment.justified,
                  "fully-justified": Word.Alignment.justified,
                  distributed: Word.Alignment.left, // fallback for distributed
                };

                const alignValue = typeof op.value === "string" ? op.value.toLowerCase() : "";
                if (alignmentMap[alignValue]) {
                  paragraphAny.alignment = alignmentMap[alignValue];
                  message += (message ? " | " : "") + `Set alignment to ${op.value}`;
                  applied = true;
                } else {
                  message += (message ? " | " : "") + `Invalid alignment value: ${op.value}`;
                }
                break;

              case "font":
                if (op.fontName) {
                  paragraphAny.font.name = op.fontName;
                }
                if (op.fontSize !== undefined) {
                  const parsedSize =
                    typeof op.fontSize === "string"
                      ? parseInt(op.fontSize.replace(/[^0-9.]/g, ""), 10)
                      : op.fontSize;
                  if (!isNaN(parsedSize)) {
                    paragraphAny.font.size = parsedSize;
                  }
                }
                message += (message ? " | " : "") + `Changed font to ${op.fontName || "new style"}`;
                applied = true;
                break;

              default:
                message += (message ? " | " : "") + `Unknown formatting operation type: ${op.type}`;
            }
          }

          await context.sync();
        }
      } catch (wordError) {
        console.error("Error inside Word.run for formatting:", wordError);
        message = `Word API error: ${wordError.message}`;
        applied = false;
        throw wordError;
      }
    });

    return {
      success: true,
      applied,
      message,
      paragraphIndex: actualParagraphIndex,
      foundInDocument: foundInDoc,
      previous_state: previousState,
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
    let foundInDoc = true;
    let previousState: any = null;

    await Word.run(async (context) => {
      try {
        const body = context.document.body;
        const target = await searchRobust(body, searchText, 0, context);

        if (target) {
          const paragraphAny = target.paragraphs.getFirst() as any;
          paragraphAny.load([
            "keepWithNext",
            "pageBreakBefore",
            "widowControl",
            "lineSpacing",
            "alignment",
          ]);
          paragraphAny.font.load(["name", "size"]);
          await context.sync();

          previousState = {
            type: "search",
            searchText: searchText,
            keepWithNext: paragraphAny.keepWithNext,
            pageBreakBefore: paragraphAny.pageBreakBefore,
            widowControl: paragraphAny.widowControl,
            lineSpacing: paragraphAny.lineSpacing,
            alignment: paragraphAny.alignment,
            fontName: paragraphAny.font.name,
            fontSize: paragraphAny.font.size,
          };

          const operations = Array.isArray(operation) ? operation : [operation];

          for (const op of operations) {
            switch (op.type) {
              case "keep_with_next":
                const keepVal = op.value === true || String(op.value).toLowerCase() === "true";
                paragraphAny.keepWithNext = keepVal;
                message +=
                  (message ? " | " : "") +
                  (keepVal ? 'Enabled "Keep with next"' : 'Disabled "Keep with next"');
                applied = true;
                break;

              case "page_break_before":
                const pbVal = op.value === true || String(op.value).toLowerCase() === "true";
                paragraphAny.pageBreakBefore = pbVal;
                message +=
                  (message ? " | " : "") +
                  (pbVal ? "Enabled page break before" : "Disabled page break before");
                applied = true;
                break;

              case "widow_orphan_control":
                const woVal = op.value === true || String(op.value).toLowerCase() === "true";
                paragraphAny.widowControl = woVal;
                message +=
                  (message ? " | " : "") +
                  (woVal ? "Enabled widow/orphan control" : "Disabled widow/orphan control");
                applied = true;
                break;

              case "line_spacing":
                const parsedSearchLineSpacing =
                  typeof op.value === "string"
                    ? parseInt(op.value.replace(/[^0-9.]/g, ""), 10)
                    : op.value;
                if (
                  typeof parsedSearchLineSpacing === "number" &&
                  !isNaN(parsedSearchLineSpacing)
                ) {
                  paragraphAny.lineSpacing = parsedSearchLineSpacing;
                  message +=
                    (message ? " | " : "") + `Set line spacing to ${parsedSearchLineSpacing}`;
                  applied = true;
                } else {
                  message += (message ? " | " : "") + `Invalid line spacing value: ${op.value}`;
                }
                break;

              case "alignment":
                const alignmentMap: Record<string, Word.Alignment> = {
                  left: Word.Alignment.left,
                  right: Word.Alignment.right,
                  center: Word.Alignment.centered,
                  justified: Word.Alignment.justified,
                  justify: Word.Alignment.justified,
                  "fully justified": Word.Alignment.justified,
                  "fully-justified": Word.Alignment.justified,
                  distributed: Word.Alignment.left, // fallback for distributed
                };

                const searchAlignValue = typeof op.value === "string" ? op.value.toLowerCase() : "";
                if (alignmentMap[searchAlignValue]) {
                  paragraphAny.alignment = alignmentMap[searchAlignValue];
                  message += (message ? " | " : "") + `Set alignment to ${op.value}`;
                  applied = true;
                } else {
                  message += (message ? " | " : "") + `Invalid alignment value: ${op.value}`;
                }
                break;

              case "font":
                if (op.fontName) {
                  paragraphAny.font.name = op.fontName;
                }
                if (op.fontSize !== undefined) {
                  const parsedSize =
                    typeof op.fontSize === "string"
                      ? parseInt(op.fontSize.replace(/[^0-9.]/g, ""), 10)
                      : op.fontSize;
                  if (!isNaN(parsedSize)) {
                    paragraphAny.font.size = parsedSize;
                  }
                }
                message += (message ? " | " : "") + `Changed font to ${op.fontName || "new style"}`;
                applied = true;
                break;

              default:
                message += (message ? " | " : "") + `Unknown formatting operation type: ${op.type}`;
            }
          }

          await context.sync();
        } else {
          message = `Could not find paragraph containing "${searchText}"`;
          applied = false;
          foundInDoc = false;
        }
      } catch (wordError) {
        console.error("Error inside Word.run for search and format:", wordError);
        message = `Word API error: ${wordError.message}`;
        applied = false;
        throw wordError;
      }
    });

    return {
      success: true,
      applied,
      message,
      paragraphIndex: foundParagraphIndex,
      foundInDocument: foundInDoc,
      previous_state: previousState,
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

export async function applyGlobalFormatting(
  operation: any,
  title: string
): Promise<FormattingResult> {
  try {
    let message = "";
    let applied = false;
    let foundInDoc = false;
    let previousState: any = null;

    await Word.run(async (context) => {
      try {
        if (title.toLowerCase().includes("footnote") && context.document.body.footnotes) {
          const footnotes = context.document.body.footnotes;
          footnotes.load("items");
          await context.sync();

          for (let i = 0; i < footnotes.items.length; i++) {
            footnotes.items[i].body.paragraphs.load("items");
          }
          await context.sync();

          for (let i = 0; i < footnotes.items.length; i++) {
            const fn = footnotes.items[i];
            const paragraphs = fn.body.paragraphs.items;

            for (let j = 0; j < paragraphs.length; j++) {
              (paragraphs[j] as any).font.load(["name", "size"]);
            }
          }
          await context.sync();

          const states: any[] = [];
          for (let i = 0; i < footnotes.items.length; i++) {
            const fn = footnotes.items[i];
            const paragraphs = fn.body.paragraphs.items;

            for (let j = 0; j < paragraphs.length; j++) {
              const font = (paragraphs[j] as any).font;
              states.push({
                footnoteIndex: i,
                paragraphIndex: j,
                fontName: font.name,
                fontSize: font.size,
              });
            }

            const operations = Array.isArray(operation) ? operation : [operation];
            for (const op of operations) {
              if (op.type === "font" || op.type === "fontSize") {
                let parsedSize: number | undefined;
                if (op.fontSize !== undefined) {
                  parsedSize =
                    typeof op.fontSize === "string"
                      ? parseInt(op.fontSize.replace(/[^0-9.]/g, ""), 10)
                      : op.fontSize;
                }

                for (let j = 0; j < paragraphs.length; j++) {
                  const font = (paragraphs[j] as any).font;
                  if (op.fontName) font.name = op.fontName;
                  if (parsedSize !== undefined && !isNaN(parsedSize)) {
                    font.size = parsedSize;
                  }
                }
                applied = true;
                foundInDoc = true;
              }
            }
          }
          previousState = {
            type: "global_footnotes",
            states,
          };
          if (applied) {
            message = `Applied formatting to ${footnotes.items.length} footnotes`;
          } else {
            message = `No formatting applied to footnotes`;
          }
          await context.sync();
        } else {
          foundInDoc = false;
          message = "Global formatting not supported for this rule or missing API support";
        }
      } catch (wordError) {
        console.error("Error inside Word.run for global formatting:", wordError);
        message = `Word API error: ${wordError.message}`;
        foundInDoc = false;
        throw wordError;
      }
    });

    return {
      success: true,
      applied,
      message,
      foundInDocument: foundInDoc,
      previous_state: previousState,
    };
  } catch (e: any) {
    console.error("Failed to apply global formatting:", e);
    return {
      success: false,
      applied: false,
      message: `Failed to apply formatting: ${e.message || "Unknown error"}`,
      foundInDocument: false,
      previous_state: null,
    };
  }
}

/**
 * Undoes a formatting operation using the previously saved state
 */
export async function undoFormatting(
  undoState: any
): Promise<{ success: boolean; message: string }> {
  try {
    if (!undoState) {
      return { success: false, message: "No undo state provided" };
    }

    await Word.run(async (context) => {
      if (undoState.type === "paragraph") {
        const paragraphs = context.document.body.paragraphs;
        paragraphs.load("items");
        await context.sync();

        if (undoState.paragraphIndex >= 0 && undoState.paragraphIndex < paragraphs.items.length) {
          const targetParagraph = paragraphs.items[undoState.paragraphIndex];
          const paragraphAny = targetParagraph as any;
          if (undoState.keepWithNext !== undefined)
            paragraphAny.keepWithNext = undoState.keepWithNext;
          if (undoState.pageBreakBefore !== undefined)
            paragraphAny.pageBreakBefore = undoState.pageBreakBefore;
          if (undoState.widowControl !== undefined)
            paragraphAny.widowControl = undoState.widowControl;
          if (undoState.lineSpacing !== undefined) paragraphAny.lineSpacing = undoState.lineSpacing;
          if (undoState.alignment !== undefined) paragraphAny.alignment = undoState.alignment;

          if (undoState.fontName) paragraphAny.font.name = undoState.fontName;
          if (undoState.fontSize) paragraphAny.font.size = undoState.fontSize;
        }
      } else if (undoState.type === "search") {
        const body = context.document.body;
        const target = await searchRobust(body, undoState.searchText, 0, context);
        if (target) {
          const paragraphAny = target.paragraphs.getFirst() as any;
          if (undoState.keepWithNext !== undefined)
            paragraphAny.keepWithNext = undoState.keepWithNext;
          if (undoState.pageBreakBefore !== undefined)
            paragraphAny.pageBreakBefore = undoState.pageBreakBefore;
          if (undoState.widowControl !== undefined)
            paragraphAny.widowControl = undoState.widowControl;
          if (undoState.lineSpacing !== undefined) paragraphAny.lineSpacing = undoState.lineSpacing;
          if (undoState.alignment !== undefined) paragraphAny.alignment = undoState.alignment;

          if (undoState.fontName) paragraphAny.font.name = undoState.fontName;
          if (undoState.fontSize) paragraphAny.font.size = undoState.fontSize;
        }
      } else if (undoState.type === "global_footnotes") {
        const footnotes = context.document.body.footnotes;
        if (footnotes) {
          footnotes.load("items");
          await context.sync();

          for (let i = 0; i < footnotes.items.length; i++) {
            footnotes.items[i].body.paragraphs.load("items");
          }
          await context.sync();

          for (const state of undoState.states) {
            if (state.footnoteIndex < footnotes.items.length) {
              const paragraphs = footnotes.items[state.footnoteIndex].body.paragraphs.items;
              if (state.paragraphIndex < paragraphs.length) {
                const font = (paragraphs[state.paragraphIndex] as any).font;
                if (state.fontName) font.name = state.fontName;
                if (state.fontSize) font.size = state.fontSize;
              }
            }
          }
        }
      }
      await context.sync();
    });

    return { success: true, message: "Formatting reverted successfully" };
  } catch (e: any) {
    console.error("Failed to undo formatting:", e);
    return { success: false, message: e.message || "Unknown error" };
  }
}
