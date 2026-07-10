# TODO — Known Gaps

- [ ] **CI is frontend-only** — no Python lint/test, no Docker image build, no CD pipeline
- [ ] **No production runtime config** — no gunicorn workers, no nginx, no TLS termination, no docker-compose.prod.yml
- [ ] **Qdrant has no healthcheck** in docker-compose (unlike Postgres/Redis)
- [ ] **No reverse proxy** — backend uvicorn and frontend webpack-dev-server exposed directly
- [ ] **Chat is stubbed** — both frontend (`ChatInput.tsx`) and backend (`/documents/:id/chat`) are placeholder

---

# Code Smells — Frontend (2026-07-10 review)

## Top 5 Highest-Impact Refactors

| Priority | Refactor | Files Affected | Est. Impact |
|----------|----------|-----------------|-------------|
| **1** | Extract `withWordRun<T>()` wrapper for Word.run boilerplate | 6 word/ files | Eliminates ~60% of word/ duplication |
| **2** | Decompose `SuggestionsTab.tsx` (hook + typed card + resolve helper) | 1 file (968→~200 lines) | Fixes 5 high-severity smells at once |
| **3** | Centralize response unwrapping in Axios interceptor | All 7 API files | Eliminates ~15 `data.data ?? data` calls |
| **4** | Consolidate CSS design tokens into single file | 2 CSS files | Resolves unpredictable token conflicts |
| **5** | Extract `useFindingActions` hook + `Record`-based state | SuggestionsTab | Removes 15x duplicated Set-update pattern |

## High Severity (16)

### Architecture / Component Design

- [ ] **H-C1. God Component: `SuggestionsTab.tsx` — 968 lines** — Owns 6+ distinct concerns (finding filtering, text replacement, formatting fixes, comments, undo, batch ops, card rendering). Extract `useFindingActions` hook + `SuggestionCard` typed component. Target ~150-200 lines.
- [ ] **H-C2. Duplicated "update ID sets" pattern 15+ times in SuggestionsTab.tsx** — Same three-line `setAcceptedIds`/`setRejectedIds`/`setCommentedIds` pattern at lines 135-137, 154-156, 191-200, 233-244, 304-314, 345-355, 383-393, 448-456, 484-494, 530-532, 585-590, 600-606, 625-630, 649-654, 668-673, 706-710. Extract single `resolveFindingLocally(id, status)` helper or use `Record<string, 'open'|'accepted'|'rejected'|'commented'>` map.
- [ ] **H-C3. `handleAccept` and `handleAcceptFormatting` near-identical 150-line handlers** — SuggestionsTab.tsx lines 112-260 vs 262-372. Same structure; only the Word API call differs. Extract `processFinding(finding, wordOperation)` with callback.
- [ ] **H-C4. `SuggestionCard` props typed as `any`** — SuggestionsTab.tsx line 817. All 17 props untyped. Define `SuggestionCardProps` interface.
- [ ] **H-C5. `handleAcceptAll` sequentially awaits every finding (blocking)** — SuggestionsTab.tsx lines 555-682. `for...of` with `await` means 50 findings take minutes. Use `Promise.allSettled` on chunks or batch backend calls.
- [ ] **H-C6. JWT payload parsing duplicated 3x with inline `atob`** — TaskPane.tsx lines 27-33, 51-57, 151-158. Fragile (no base64url padding). Extract `parseJwtPayload(token)` utility.

### API Layer

- [ ] **H-A1. Response unwrapping `data.data ?? data` repeated ~15 times** — ai-jobs.ts, qc.ts, documents.ts, config.ts. Add envelope unwrapping in Axios response interceptor in client.ts. Eliminates all duplication.
- [ ] **H-A2. `documents.ts` bypasses Axios client entirely** — Lines 23-28, 70-71. `downloadDocument` and `syncActiveDocument` use raw `fetch` with manual auth headers, missing interceptor logic. Use `apiClient` with `responseType: 'blob'` or extract `fetchWithAuth` helper.
- [ ] **H-A3. `syncActiveDocument` is 50+ lines with 3 sequential API operations** — documents.ts lines 46-98. Mixes infrastructure (Azure blob headers) with business logic. Split into `getOrCreateClientId()`, `createDocumentRecord()`, `uploadDocumentBlob()`.
- [ ] **H-A4. `qcApi.getFindings` has redundant fallback chains** — qc.ts lines 8-24. `item.title || loc.title || item.title || ""` — third operand unreachable. Remove duplicates; extract `normalizeQCFinding(raw)`.

### Word Integration

- [ ] **H-W1. Massive copy-paste: duplicated `Word.run` boilerplate across 6 files (~10 copies)** — comments.ts, tracking.ts, replace.ts, formatting.ts, metadata.ts, selection.ts. Same try/Word.run/try/catch/catch + AccessDenied check everywhere. Extract `withWordRun<T>(fn)` wrapper.
- [ ] **H-W2. Entire formatting switch/case duplicated between two functions** — formatting.ts lines 76-154 vs 207-284. Character-for-character identical. `alignmentMap` also duplicated. Extract `applyOperationsToParagraph(paragraph, operations)` + module-level `alignmentMap`.
- [ ] **H-W3. `KLARA_DEBUG_NAV` declared after usage — latent crash bug** — utils.ts line 186 (usage) vs 354 (declaration). `const` is not hoisted; setting to `true` would crash. Move declaration to file top.
- [ ] **H-W4. `searchWithVariations` has unbounded recursion via footnote search** — utils.ts lines 332-348. No depth guard on recursive footnote calls. Add `maxDepth` parameter (default 1).

## Medium Severity (26)

### Type Safety

- [ ] **M-T1. `getMe()` returns `Promise<any>`** — auth.ts line 21. Should return `Promise<AuthUser>`.
- [ ] **M-T2. `getChecklistStatuses()` returns `Promise<any[]>`** — qc.ts line 53. Should return `ChecklistItem[]`.
- [ ] **M-T3. `any` types in wordFeaturesApi.ts interfaces** — Lines 15, 24, 36: `fixes: any[]`, `range?: any`, `conflict_data: any`. Define proper types.
- [ ] **M-T4. `FormattingOperation` imported but unused in formatting.ts** — Line 2. `operation: any` everywhere. Use the imported type.
- [ ] **M-T5. `searchScope: any` in utils.ts** — Line 138. Constrain to actual call-site types (`Word.Body | Word.Paragraph`).
- [ ] **M-T6. Excessive `any` casts on Office.js objects** — 6 locations across metadata.ts, utils.ts, formatting.ts.

### Duplication & Inconsistency

- [ ] **M-D1. Module-level `loadStoredTokens()` side effect on import** — client.ts line 46. Importing for types triggers localStorage access.
- [ ] **M-D2. 3x duplicated `localStorage` try/catch in client.ts** — Lines 16-22, 26-32, 36-43. Extract `safeLocalStorage` wrapper.
- [ ] **M-D3. `wordFeaturesApi` doesn't unwrap responses** — Unlike all other API modules. Apply same pattern or fix at interceptor level.
- [ ] **M-D4. 3 near-identical comment-creation functions in comments.ts** — `createKlaraComment`, `createKlaraCommentInParagraph`, `createKlaraCommentAtParagraph`. Unify with options object.
- [ ] **M-D5. 2 near-identical tracked-change functions in tracking.ts** — `createSimulatedTrackedChange`, `createSimulatedTrackedChangeInParagraph`. One function with optional `paragraphIndex`.
- [ ] **M-D6. Duplicated footnote search pattern** — utils.ts lines 332-348 + selection.ts lines 16-27. Extract `searchIncludingFootnotes()` helper.
- [ ] **M-D7. Local interfaces in config.ts instead of shared types.ts** — `PocRule` and `MS365Config` should move to types.ts.

### UX & State Management

- [ ] **M-U1. Inline styles scattered throughout all components** — 20+ instances across TaskPane, ChecksTab, WorkflowsTab, SuggestionsTab. Move to CSS classes.
- [ ] **M-U2. No scroll-to-bottom on new chat messages** — ChatInput.tsx lines 48-55. Add `useRef` + `scrollIntoView`.
- [ ] **M-U3. Magic `-50`/`-49` for chat message cap** — TaskPane.tsx line 315 + ChatInput.tsx line 49. Define `MAX_CHAT_MESSAGES` constant.
- [ ] **M-U4. `error` state misused for success notifications** — SuggestionsTab.tsx lines 85-91. Success summaries appear in red `--danger` banner. Introduce `notification` state with `type: 'error'|'success'|'info'`.
- [ ] **M-U5. Stub `setTimeout` response in production ChatInput** — ChatInput.tsx line 27. Gate behind feature flag or hide chat UI.
- [ ] **M-U6. `handleNavigate` useCallback has misleading dependencies** — SuggestionsTab.tsx line 110. Lists `acceptedIds`/`rejectedIds` but doesn't reference them.
- [ ] **M-U7. Prop drilling: `findings` + `docId` to all tabs** — TaskPane.tsx line 145. Let each tab call `useFindings(docId)` directly.

### CSS & Code Quality

- [ ] **M-Q1. Conflicting CSS design token systems** — `taskpane.css` (hex, no dark mode) vs `global-styles.css` (oklch, dark mode). Consolidate into single file.
- [ ] **M-Q2. Outlook mailbox API in Word add-in scaffold code** — commands.ts lines 17-30. Dead code — replace or remove.
- [ ] **M-Q3. `replaceTextInParagraph` is 200 lines, 5 nesting levels, 20+ emoji console.logs** — replace.ts lines 14-235. Split into `findTextLocation()` + `replaceAtRange()`. Gate logs behind flag.

## Low Severity (16)

- [ ] **L1. `isActionableFinding` always returns `true`** — SuggestionsTab.tsx lines 15-19. Dead code — remove.
- [ ] **L2. `HeroList.tsx` is entirely unused** — Yeoman template leftover. Remove after confirming no imports.
- [ ] **L3. HeroList uses deprecated `fontColor` + background color as text color** — Lines 27, 37. Use `color: tokens.colorNeutralForeground1`.
- [ ] **L4. Fake progress bar with `Math.random()`** — WorkflowsTab.tsx lines 53-70. Use indeterminate spinner or backend `progress_pct`.
- [ ] **L5. Poll timer not cleared on unmount** — WorkflowsTab.tsx lines 72-117. Memory leak.
- [ ] **L6. `handleRunChecks` not wrapped in `useCallback`** — ChecksTab.tsx lines 91-106. Inconsistent with siblings.
- [ ] **L7. Login inputs lack `aria-label`** — TaskPane.tsx lines 83-98. `placeholder` alone is inaccessible.
- [ ] **L8. Icon-only buttons missing `aria-label`** — TaskPane.tsx + ChatInput.tsx. Add `aria-label` to all icon-only buttons.
- [ ] **L9. Dead try/catch with commented-out thought process** — selection.ts lines 38-42. Remove.
- [ ] **L10. `highlightRange`/`clearHighlights` swallow all errors silently** — selection.ts lines 113-135. Add `console.warn`.
- [ ] **L11. Redundant 3-level try/catch nesting in `getDocumentMetadata`** — metadata.ts lines 3-33. Simplify.
- [ ] **L12. `console.log` used for errors** — taskpane.ts line 13. Should be `console.error`.
- [ ] **L13. Unused imports in 4 word/ files** — comments.ts, metadata.ts, tracking.ts, selection.ts. Clean up imports.
- [ ] **L14. `undoSimulatedTrackedChange` is trivial alias** — tracking.ts lines 217-222. Re-export or remove.
- [ ] **L15. `metadata.ts` mixes unrelated concerns** — Metadata + blob export + health check. Split into separate modules.
- [ ] **L16. Magic numbers throughout** — `65536` (metadata.ts:82), `0, 50` (metadata.ts:160), `text.length > 15` (utils.ts:101), pixel values in CSS. Extract named constants.
