# Klara Taskpane Architecture

## Overview
The Klara Word Add-in taskpane follows a strictly modular architecture utilizing React and custom hooks. The design prioritizes a strict **Separation of Concerns**, splitting UI rendering, business logic, and external API integrations into independent files. 

This ensures that the massive complexity of interacting with the Office.js API and managing optimistic updates does not bleed into the visual presentation of the suggestions.

## Core Architecture

The suggestions feature is broken down into three primary components:

### 1. `SuggestionsTab.tsx` (Container Component)
This is the lean container component. It is completely decoupled from how suggestions are actually processed or interacted with in Microsoft Word.
*   **Responsibilities**: 
    *   Initializes the `useFindingsActions` hook.
    *   Manages purely transient UI state (e.g., `editingId`, `editDraft`) for the inline editing mode.
    *   Maps over the `openFindings` and `resolvedFindings` to render the cards.
    *   Renders empty states and loading spinners.

### 2. `useFindingsActions.ts` (Business Logic Hook)
This custom hook acts as the "Brain" of the suggestions tab. It handles all asynchronous operations and local state tracking.
*   **Responsibilities**:
    *   **Office.js Bindings**: Wraps all interactions with Word (via `../word.ts`), including `searchAndSelect`, `applyParagraphFormatting`, `replaceText`, and `undoFormatting`.
    *   **State Management**: Tracks the lifecycle of findings using `Set` data structures (`acceptedIds`, `rejectedIds`, `commentedIds`).
    *   **Undo Engine**: Maintains the `localUndoStates` mapping, allowing for immediate optimistic undo actions without waiting for backend state re-syncs.
    *   **Derived Data**: Computes `openFindings` and `resolvedFindings` by filtering the raw API data against the local lifecycle state.

### 3. `SuggestionCard.tsx` (Presentation Component)
A highly focused, reusable component responsible exclusively for rendering a single suggestion card.
*   **Responsibilities**:
    *   Renders the title, description, severity badges, and inline text diffs.
    *   Renders contextual buttons (Accept, Reject, Undo, Comment) based on the finding's resolution status.
    *   Provides controlled inputs for editing the suggestion (e.g., numeric inputs for font sizes, textareas for text replacement).

---

## Data and Event Flow

```mermaid
graph TD
    API[(Backend /qc API)] -->|Raw Findings| ST(SuggestionsTab)
    
    subgraph Frontend
        ST -->|Passes findings| Hook(useFindingsActions)
        Hook -->|Returns derived state & handlers| ST
        
        ST -->|Props: finding, isResolved, handlers| SC(SuggestionCard)
        SC -->|onClick / onAccept / onUndo| Hook
    end
    
    subgraph Office.js Context
        Hook -->|Word.run() Commands| WordAPI[Microsoft Word API]
        WordAPI -->|FormattingResult| Hook
    end
    
    Hook -->|Optimistic Updates| Hook
    Hook -->|Syncs changes| API
```

## Undo System Architecture

The undo system was designed to handle the latency between the Office.js document changes and the backend synchronization.

1. **Accepting a Finding**:
   When a user accepts a formatting suggestion, the `handleAcceptFormatting` method executes the change via Office.js. The Word API returns a `FormattingResult` which includes a `previous_state` payload (capturing the exact state of the text *before* the modification).
2. **Local Undo Cache**:
   Instead of immediately waiting for the backend to persist this state, the hook immediately caches the `previous_state` in the `localUndoStates` map. This optimistic update instantly flags the card as "Accepted" in the UI.
3. **Executing Undo**:
   If the user immediately clicks "Undo", `handleUndo` retrieves the `previous_state` directly from `localUndoStates` (or falls back to the backend's `resolution_notes`), applies the perfect reverse format, and restores the finding to the `openFindings` queue.

## Extending the Architecture
*   **Adding New UI States**: Modify `SuggestionCard.tsx`. If it requires tracking new transient input data, add it to `SuggestionsTab.tsx`.
*   **Adding New Word Actions**: Implement the Office.js bindings in `word.ts`, then expose a new handler in `useFindingsActions.ts` (e.g., `handleHighlight`). Do not put Office.js logic directly in the React components.
