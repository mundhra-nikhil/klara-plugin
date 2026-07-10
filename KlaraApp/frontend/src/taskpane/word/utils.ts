
/**
 * Generate multiple search variations for special characters
 * This helps handle different Unicode representations and encoding issues
 */
export function generateSearchVariations(text: string): string[] {
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

  // Multi-paragraph flattened text variation:
  // If AI flattened paragraph breaks into spaces, strict search fails.
  // We escape Word's reserved wildcard chars, then replace all spaces with '*' to match across paragraphs.
  if (text.length > 15 && text.length < 200) {
    // Word wildcard reserved chars: \ ( ) [ ] { } < > * ? @
    const escaped = text.replace(/([\\()\[\]{}<>*?@])/g, '\\$1');
    const starVariation = escaped.replace(/\s+/g, "*");
    if (starVariation !== escaped && starVariation.length < 255) {
      variations.push(starVariation);
    }
  }

  // Word separates TOC numbers and list items with tabs, which often get extracted as spaces.
  // '^w' is Word's special character for 'any white space' (spaces, tabs, non-breaking spaces).
  const whitespaceVariation = text.replace(/\s+/g, "^w");
  if (whitespaceVariation !== text) {
    variations.push(whitespaceVariation);
  }

  // Word TOCs often use a tab with dot leaders, which the AI might extract as literal dots.
  // Replace 2 or more dots (or sequences of dots and spaces) with '^w' (any white space).
  if (text.includes("..")) {
    const dotVariation = text.replace(/[\s\.]*\.{2,}[\s\.]*/g, "^w");
    if (dotVariation !== text) {
      variations.push(dotVariation);
    }
  }

  return Array.from(new Set(variations));
}

/**
 * Robust search that handles text spanning multiple paragraphs by matching the start and end chunks.
 *
 * When the search text spans multiple paragraphs (common in AI-flattened TOA entries), wildcard
 * variations in searchWithVariations can match but return a range collapsed to the first paragraph.
 * To avoid that, we check whether the text footprint is multi-paragraph first and, if so, prefer
 * the explicit paragraph-offset reconstruction over the wildcard fast path.
 */
export async function searchRobust(
  searchScope: any,
  text: string,
  occurrence: number,
  context: Word.RequestContext
): Promise<Word.Range | null> {
  const stripRegex = /[^a-zA-Z0-9]+/g;
  const normalizedSearch = text.replace(stripRegex, "").toLowerCase();

  // Pre-compute paragraph offsets so we can decide if the text is multi-paragraph
  // without an extra sync later.
  const body = context.document.body;
  const paragraphs = body.paragraphs;
  context.load(paragraphs, "items/text");
  await context.sync();

  let fullText = "";
  const pStarts: number[] = [];
  for (let i = 0; i < paragraphs.items.length; i++) {
    pStarts.push(fullText.length);
    fullText += (paragraphs.items[i].text || "").replace(stripRegex, "").toLowerCase();
  }

  const matchIndex = fullText.indexOf(normalizedSearch);

  // Determine whether the search text spans multiple paragraphs in the document.
  let isMultiParagraph = false;
  let startP = 0;
  let endP = 0;
  if (matchIndex !== -1) {
    for (let i = 0; i < pStarts.length; i++) {
      if (pStarts[i] <= matchIndex) startP = i;
    }
    const matchEnd = matchIndex + normalizedSearch.length;
    endP = startP;
    for (let i = startP; i < pStarts.length; i++) {
      if (pStarts[i] < matchEnd) endP = i;
    }
    isMultiParagraph = endP > startP;
  }

  if (isMultiParagraph) {
    // ── Multi-paragraph path: use explicit paragraph reconstruction ──
    // searchWithVariations wildcard hits (e.g. starVariation with spaces→'*') can match
    // across paragraph marks but return a range collapsed to the first paragraph's run.
    // Bypass that by building the range from paragraph offsets directly.
    const startParagraph = paragraphs.items[startP];
    const endParagraph = paragraphs.items[endP];

    if (KLARA_DEBUG_NAV) {
      console.log(`[KLARA-NAV] Multi-paragraph match: startP=${startP}, endP=${endP}`);
      console.log(`[KLARA-NAV] startP text: "${(startParagraph as any).text?.substring(0, 80)}"`);
      console.log(`[KLARA-NAV] endP text:   "${(endParagraph as any).text?.substring(0, 80)}"`);

      // Diagnostic: check if the paragraph is inside a table (TOA entries often are)
      try {
        const parentTable = (startParagraph as any).parentTableOrNullObject;
        (context as any).load(parentTable, "isNull");
        await context.sync();
        if (parentTable && !parentTable.isNull) {
          console.log(`[KLARA-NAV] startParagraph is INSIDE a table`);
        } else {
          console.log(`[KLARA-NAV] startParagraph is NOT inside a table`);
        }
      } catch (diagErr) {
        console.warn(`[KLARA-NAV] parentTableOrNullObject check failed:`, diagErr);
      }

      // Diagnostic: check style (e.g. 'TOA', 'TOA Heading' suggests a Table of Authorities)
      try {
        (context as any).load(startParagraph, "styleBuiltIn");
        await context.sync();
        console.log(`[KLARA-NAV] startParagraph styleBuiltIn: ${(startParagraph as any).styleBuiltIn}`);
      } catch (diagErr) {
        console.warn(`[KLARA-NAV] styleBuiltIn check failed:`, diagErr);
      }
    }

    // Split by whitespace instead of stripRegex so that we preserve trailing punctuation 
    // like ')' in '1998)'. searchWithVariations already handles punctuation fallbacks.
    const words = text.trim().split(/\s+/).filter(w => w.length > 0);
    if (words.length > 0) {
      const startWord = words.find(w => w.replace(/[^a-zA-Z0-9]/g, '').length >= 4) || words[0];
      const endWord = [...words].reverse().find(w => w.replace(/[^a-zA-Z0-9]/g, '').length >= 4) || words[words.length - 1];

      const startTarget = await searchWithVariations(startParagraph, startWord, 0);
      const endTarget = await searchWithVariations(endParagraph, endWord, -1);

      if (startTarget && endTarget) {
        return startTarget.expandTo(endTarget);
      }
    }

    return startParagraph.getRange("Start").expandTo(endParagraph.getRange("End"));
  }

  // ── Single-paragraph fast path ──
  // Text either lives in one paragraph or wasn't found at all — let searchWithVariations
  // handle it with all its Unicode/wildcard/whitespace heuristics.
  let target = await searchWithVariations(searchScope, text, occurrence);
  if (target) return target;

  return null;
}

/**
 * Enhanced search function that tries multiple text variations
 */
export async function searchWithVariations(
  searchScope: any,
  text: string,
  occurrence: number = 0
): Promise<Word.Range | null> {
  const variations = generateSearchVariations(text);
  console.log(`🔍 Trying ${variations.length} search variations for "${text}"`);

  for (let i = 0; i < variations.length; i++) {
    const variation = variations[i];
    console.log(`🔍 Variation ${i + 1}/${variations.length}: "${variation}"`);

    try {
      // Try exact match
      let searchResults = searchScope.search(variation, {
        matchCase: true,
        ignorePunct: false,
        ignoreSpace: false,
      });
      searchResults.context.load(searchResults, "items");
      await searchResults.context.sync();

      const getOccurrence = (items: Word.Range[]) => {
        if (items.length === 0) return null;
        if (occurrence === -1) return items[items.length - 1];
        if (items.length > occurrence) return items[occurrence];
        return null;
      };

      if (searchResults.items.length > 0) {
        const item = getOccurrence(searchResults.items);
        if (item) {
          console.log(`✅ Found with exact match: "${variation}"`);
          return item;
        }
      }

      // Try case-insensitive
      searchResults = searchScope.search(variation, {
        matchCase: false,
        ignorePunct: true,
        ignoreSpace: true,
      });
      searchResults.context.load(searchResults, "items");
      await searchResults.context.sync();

      if (searchResults.items.length > 0) {
        const item = getOccurrence(searchResults.items);
        if (item) {
          console.log(`✅ Found with relaxed match: "${variation}"`);
          return item;
        }
      }

      // Try wildcard for special characters if not already a wildcard string
      if (variation.includes("*") || variation.includes("?") || variation.includes("^")) {
        searchResults = searchScope.search(variation, { matchWildcards: true });
        searchResults.context.load(searchResults, "items");
        await searchResults.context.sync();

        if (searchResults.items.length > 0) {
          const item = getOccurrence(searchResults.items);
          if (item) {
            console.log(`✅ Found with explicit wildcard: "${variation}"`);
            return item;
          }
        }
      } else if (/[^\w\s]/.test(variation)) {
        const wildcard = variation.replace(/[^\w\s]/g, "?");
        searchResults = searchScope.search(wildcard, { matchWildcards: true });
        searchResults.context.load(searchResults, "items");
        await searchResults.context.sync();

        if (searchResults.items.length > 0) {
          const item = getOccurrence(searchResults.items);
          if (item) {
            console.log(`✅ Found with generated wildcard: "${wildcard}"`);
            return item;
          }
        }
      }
    } catch (e) {
      console.warn(`⚠️ Search failed for variation "${variation}":`, e);
      continue;
    }
  }

  if (searchScope.footnotes) {
    try {
      const context = searchScope.context;
      const footnotes = searchScope.footnotes;
      footnotes.load("items");
      await context.sync();
      for (let i = 0; i < footnotes.items.length; i++) {
        const fnTarget = await searchWithVariations(footnotes.items[i].body, text, 0);
        if (fnTarget) {
          console.log(`✅ Found in footnote ${i + 1}`);
          return fnTarget;
        }
      }
    } catch (e) {
      console.warn("⚠️ Footnote search failed:", e);
    }
  }

  console.log(`❌ All search variations failed for "${text}"`);
  return null;
}

const KLARA_DEBUG_NAV = false;
export function isNormalizedMatch(str1: string, str2: string): boolean {
  if (!str1 || !str2) return str1 === str2;
  const normalize = (s: string) => s.replace(/[\r\n]+/g, '\n').replace(/\s+/g, ' ').trim();
  return normalize(str1) === normalize(str2);
}
