import {
  searchRobust,
  searchWithVariations,
  isNormalizedMatch,
  generateSearchVariations,
} from "./utils";
import { replaceTextInParagraph } from "./replace";

/**
 * Creates a simulated tracked change for a text replacement
 */
export async function createSimulatedTrackedChange(
  text: string,
  replacementText: string,
  commentText: string,
  findingId: string
): Promise<{ success: boolean; message: string; foundInDocument?: boolean }> {
  try {
    let message = "";
    let success = false;
    let foundInDoc = true;

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
          const replacementRange = target.insertText(
            suggestedReplacement,
            Word.InsertLocation.after
          );

          // Format replacement text
          replacementRange.font.color = "#0000FF";
          replacementRange.font.underline = Word.UnderlineType.single;

          // Wrap in a Content Control
          const fullRange = target.expandTo(replacementRange);
          const cc = fullRange.insertContentControl();
          cc.title = `Klara Suggestion: ${findingId}`;
          cc.tag = findingId;

          // Add a comment to the original selection
          target.insertComment(
            `[Klara Suggestion] Replace "${originalText}" with "${replacementText}"\n\n${commentText}`
          );

          await context.sync();
          success = true;
          message = `Simulated tracked change created for ${findingId}`;
        } else {
          message = `Text "${text}" not found in document`;
          foundInDoc = false;
        }
      } catch (wordError: any) {
        console.error("Error creating simulated track change:", wordError);
        message = `Word API error: ${wordError.message}`;
        if (
          wordError.code === "AccessDenied" ||
          (wordError.message && wordError.message.includes("AccessDenied"))
        ) {
          foundInDoc = false;
          message = "Cannot add comments to this location (e.g., footnotes or headers).";
        }
      }
    });

    return { success, message, foundInDocument: foundInDoc };
  } catch (e: any) {
    console.error("Failed to create simulated track change:", e);
    return { success: false, message: e.message || "Unknown error", foundInDocument: false };
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
): Promise<{ success: boolean; message: string; foundInDocument?: boolean }> {
  try {
    let message = "";
    let success = false;
    let foundInDoc = true;

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

            const replacementRange = target.insertText(
              suggestedReplacement,
              Word.InsertLocation.after
            );
            replacementRange.font.color = "#0000FF";
            replacementRange.font.underline = Word.UnderlineType.single;

            const fullRange = target.expandTo(replacementRange);
            const cc = fullRange.insertContentControl();
            cc.title = `Klara Suggestion: ${findingId}`;
            cc.tag = findingId;

            target.insertComment(
              `[Klara Suggestion] Replace "${originalText}" with "${replacementText}"\n\n${commentText}`
            );

            await context.sync();
            success = true;
            message = `Simulated tracked change created in paragraph ${paragraphIndex}`;
          } else {
            message = `Text "${text}" not found in paragraph ${paragraphIndex}`;
            foundInDoc = false;
          }
        } else {
          message = `Paragraph index ${paragraphIndex} out of range`;
          foundInDoc = false;
        }
      } catch (wordError: any) {
        console.error("Error creating simulated track change:", wordError);
        message = `Word API error: ${wordError.message}`;
        if (
          wordError.code === "AccessDenied" ||
          (wordError.message && wordError.message.includes("AccessDenied"))
        ) {
          foundInDoc = false;
          message = "Cannot add comments to this location (e.g., footnotes or headers).";
        }
      }
    });

    return { success, message, foundInDocument: foundInDoc };
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
