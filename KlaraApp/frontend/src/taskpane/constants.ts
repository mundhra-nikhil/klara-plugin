export const FINDING_STATUS = {
  OPEN: 'open',
  ACCEPTED: 'accepted',
  REJECTED: 'rejected',
} as const;

export const RULE_NAMES = {
  FONT_CONSISTENCY: 'FONT CONSISTENCY',
  PARAGRAPH_JUSTIFICATION: 'JUSTIFICATION',
  TOA_COMPLETENESS: 'TOA COMPLETENESS',
} as const;

export const MANUAL_REVIEW_RULES = [
  RULE_NAMES.TOA_COMPLETENESS,
];

export const FINDING_TYPES = {
  FONT: 'font',
  ALIGNMENT: 'alignment',
} as const;

export const QUERY_KEYS = {
  FINDINGS: 'findings',
} as const;

export const REGEX_PATTERNS = {
  RESTRICTED_COMMENT_ZONES: /footnote|footer|header/i,
  NUMBERS_ONLY: /(\d+)/,
} as const;

export const MESSAGES = {
  NO_SUGGESTIONS: 'No pending suggestions',
  PROCESSING: 'Processing...',
  RESOLVED_SUGGESTIONS: 'Resolved Suggestions',
  RESTRICTED_COMMENT: 'Comments cannot be added in footnotes or headers/footers',
  API_BLOCK_PRECISE_SELECTION: 'Word API blocked precise selection',
  API_BLOCK_SELECTION: 'Word API blocked selection',
  API_BLOCK_FALLBACK: 'Word API blocked highlighting the fallback paragraph',
  API_FAILED_HIGHLIGHT: 'Failed to highlight context',
  API_FAILED_ACCEPT: 'Failed to accept finding',
  API_FAILED_REJECT: 'Failed to reject finding',
  API_FAILED_COMMENT: 'Failed to add comment',
  API_FAILED_ACCEPT_ALL: 'Failed to accept all actionable findings',
  API_FAILED_UNDO: 'Failed to undo finding',
} as const;
