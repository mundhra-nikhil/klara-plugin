import { searchRobust } from "./utils";
import type { QCFinding } from "../types";

/**
 * Result type for template application
 */
export interface TemplateApplicationResult {
  success: boolean;
  message: string;
}

export async function applyTemplateFix(
  finding: QCFinding,
  templateData: any
): Promise<TemplateApplicationResult> {
  let success = false;
  let message = "";

  try {
    await Word.run(async (context) => {
      if (!finding.original_text) {
        throw new Error("Cannot apply template without original_text to locate the target block.");
      }

      // We rely on searchRobust to find the original TOA block
      const targetRange = await searchRobust(context.document.body, finding.original_text, finding.paragraph_index || 0, context);

      if (!targetRange) {
        throw new Error(`Could not find the target text block in the document.`);
      }

      console.log(`🎯 Found target block for template insertion.`);
      
      // Clear the old text
      targetRange.clear();

      if (templateData.template_type === 'toa_list') {
        const entries = templateData.entries || [];
        
        let currentRange = targetRange;
        // Build the TOA block dynamically
        for (let i = 0; i < entries.length; i++) {
          const entry = entries[i];
          // Insert after the current range
          const paragraph = currentRange.insertParagraph("", "After");
          
          // Insert the case name and apply italics
          const caseNameRange = paragraph.insertText(entry.case_name + ", ", "End");
          caseNameRange.font.italic = true;
          
          // Insert the citation without italics
          const citationRange = paragraph.insertText(entry.citation, "End");
          citationRange.font.italic = false;

          // Apply hanging indent (e.g. 0.25 inch -> 18 points)
          paragraph.leftIndent = 18;
          paragraph.firstLineIndent = -18;
          
          currentRange = paragraph.getRange();
        }
        
        await context.sync();
        success = true;
        message = "Successfully built and inserted structured TOA.";
      } else {
        throw new Error(`Unsupported template_type: ${templateData.template_type}`);
      }
    });
  } catch (error: any) {
    console.error("Error applying template fix:", error);
    success = false;
    message = error.message || "Failed to apply structured template.";
  }

  return { success, message };
}
