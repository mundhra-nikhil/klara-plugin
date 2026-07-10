import { searchRobust, searchWithVariations, isNormalizedMatch, generateSearchVariations } from "./utils";

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
): Promise<{ success: boolean; message: string; foundInDocument?: boolean }> {
  try {
    let message = "";
    let success = false;
    let foundInDoc = true;

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
          foundInDoc = false;
        }
      } catch (wordError: any) {
        console.error("Error inside Word.run for comment creation:", wordError);
        message = `Word API error: ${wordError.message}`;
        if (wordError.code === "AccessDenied" || (wordError.message && wordError.message.includes("AccessDenied"))) {
          foundInDoc = false;
          message = "Cannot add comments to this location (e.g., footnotes or headers).";
        }
      }
    });

    return {
      success,
      message,
      foundInDocument: foundInDoc,
    };
  } catch (e: any) {
    console.error("Failed to create Klara comment:", e);
    return {
      success: false,
      message: `Failed to create comment: ${e.message || "Unknown error"}`,
      foundInDocument: false,
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
            foundInDoc = false;
          }
        } else {
          message = `Paragraph index ${paragraphIndex} out of range`;
          foundInDoc = false;
        }
      } catch (wordError: any) {
        console.error("Error inside Word.run for comment creation:", wordError);
        message = `Word API error: ${wordError.message}`;
        if (wordError.code === "AccessDenied" || (wordError.message && wordError.message.includes("AccessDenied"))) {
          foundInDoc = false;
          message = "Cannot add comments to this location (e.g., footnotes or headers).";
        }
      }
    });

    return {
      success,
      message,
      foundInDocument: foundInDoc,
    };
  } catch (e: any) {
    console.error("Failed to create Klara comment in paragraph:", e);
    return {
      success: false,
      message: `Failed to create comment: ${e.message || "Unknown error"}`,
      foundInDocument: false,
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
          const range = paragraph.getRange();
          range.insertComment(commentText);
          await context.sync();

          success = true;
          message = `Comment added by Klara AI at paragraph ${paragraphIndex} ${findingId ? `(Finding ID: ${findingId})` : ""}`;
        } else {
          message = `Paragraph index ${paragraphIndex} out of range`;
          foundInDoc = false;
        }
      } catch (wordError: any) {
        console.error("Error inside Word.run for comment creation at paragraph:", wordError);
        message = `Word API error: ${wordError.message}`;
        if (wordError.code === "AccessDenied" || (wordError.message && wordError.message.includes("AccessDenied"))) {
          foundInDoc = false;
          message = "Cannot add comments to this location (e.g., footnotes or headers).";
        }
      }
    });

    return {
      success,
      message,
      foundInDocument: foundInDoc,
    };
  } catch (e: any) {
    console.error("Failed to create Klara comment at paragraph:", e);
    return {
      success: false,
      message: `Failed to create comment: ${e.message || "Unknown error"}`,
      foundInDocument: false,
    };
  }
}

