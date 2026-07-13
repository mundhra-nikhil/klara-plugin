import React, { useState, useCallback } from 'react';
import type { QCFinding } from '../types';
import { useFindingsActions } from '../hooks/useFindingsActions';
import { SuggestionCard } from './SuggestionCard';
import { FINDING_TYPES, MESSAGES, RULE_NAMES, REGEX_PATTERNS, MANUAL_REVIEW_RULES } from '../constants';

interface SuggestionsTabProps {
  findings: QCFinding[];
  docId: string | null;
}

export function SuggestionsTab({ findings, docId }: SuggestionsTabProps) {
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editDraft, setEditDraft] = useState<Record<string, string>>({});

  const clearEdit = useCallback((id: string) => {
    setEditDraft((prev) => {
      const n = { ...prev };
      delete n[id];
      return n;
    });
  }, []);

  const {
    loading,
    error,
    commentedIds,
    openFindings,
    resolvedFindings,
    actionableFindings,
    handleNavigate,
    handleAccept,
    handleAcceptFormatting,
    handleReject,
    handleComment,
    handleUndo,
    handleAcceptAll,
    handleRejectAll
  } = useFindingsActions({ docId, findings, clearEdit });

  const getReplacement = useCallback((f: QCFinding) => {
    return editDraft[f.id] ?? f.replacement_text ?? f.suggested_fix ?? '';
  }, [editDraft]);

  const effectiveFinding = useCallback((f: QCFinding): QCFinding => {
    let replacement = getReplacement(f) || f.replacement_text;
    let description = f.description;
    let formatting_fix = f.formatting_fix;
    
    // Intercept manual review rules that the backend mistakenly sends as text replacements
    const isManualReview = MANUAL_REVIEW_RULES.some(rule => f.rule_name?.toUpperCase().includes(rule));
    if (isManualReview && replacement) {
       // Append the instruction to the description so the user can read it
       description = description ? `${description}\n\nInstruction: ${replacement}` : replacement;
       // Clear the replacement text so we don't attempt a literal text replacement
       replacement = undefined;
    }
    
    // Generic Fallback Injector for Formatting Fixes
    // If the backend sends text instructions instead of a structural formatting_fix, parse it here
    if (replacement && !formatting_fix) {
       const lowerReplacement = replacement.toLowerCase();

       // Font Consistency
       const isFontConsistency = f.rule_name?.toUpperCase().includes(RULE_NAMES.FONT_CONSISTENCY);
       if (isFontConsistency) {
         const match = replacement.match(REGEX_PATTERNS.NUMBERS_ONLY);
         if (match) {
           formatting_fix = { type: FINDING_TYPES.FONT as "font", fontSize: parseInt(match[1], 10) };
         }
       }
       // Paragraph Justification / Alignment
       else if (f.rule_name?.toUpperCase().includes(RULE_NAMES.PARAGRAPH_JUSTIFICATION) || lowerReplacement.includes('alignment') || lowerReplacement.includes('justified')) {
         if (lowerReplacement.includes('fully justified') || lowerReplacement.includes('justified')) {
           formatting_fix = { type: 'alignment', value: 'justified' };
         } else if (lowerReplacement.includes('left')) {
           formatting_fix = { type: 'alignment', value: 'left' };
         } else if (lowerReplacement.includes('right')) {
           formatting_fix = { type: 'alignment', value: 'right' };
         } else if (lowerReplacement.includes('center')) {
           formatting_fix = { type: 'alignment', value: 'center' };
         }
       }
       // Line Spacing
       else if (lowerReplacement.includes('line spacing')) {
         const match = lowerReplacement.match(/(\d+\.?\d*)/);
         if (match) {
           formatting_fix = { type: 'line_spacing', value: parseFloat(match[1]) };
         }
       }
       // Widow/Orphan Control
       else if (lowerReplacement.includes('widow') || lowerReplacement.includes('orphan')) {
         const enable = !lowerReplacement.includes('disable') && !lowerReplacement.includes('remove') && !lowerReplacement.includes('false');
         formatting_fix = { type: 'widow_orphan_control', value: enable };
       }
       // Keep with Next
       else if (lowerReplacement.includes('keep with next')) {
         const enable = !lowerReplacement.includes('disable') && !lowerReplacement.includes('remove') && !lowerReplacement.includes('false');
         formatting_fix = { type: 'keep_with_next', value: enable };
       }
       // Page Break Before
       else if (lowerReplacement.includes('page break before')) {
         const enable = !lowerReplacement.includes('disable') && !lowerReplacement.includes('remove') && !lowerReplacement.includes('false');
         formatting_fix = { type: 'page_break_before', value: enable };
       }
    }

    return {
      ...f,
      description,
      replacement_text: replacement,
      formatting_fix: formatting_fix
    };
  }, [getReplacement]);

  const startEdit = useCallback((f: QCFinding) => {
    setEditDraft((prev) => ({ ...prev, [f.id]: getReplacement(f) }));
    setEditingId(f.id);
  }, [getReplacement]);

  const cancelEdit = useCallback(() => setEditingId(null), []);

  const saveEdit = useCallback(() => {
    setEditingId(null);
  }, []);

  if (loading) {
    return (
      <div className="klara-loading">
        <div className="klara-loading-spinner" />
        {MESSAGES.PROCESSING}
      </div>
    );
  }

  if (openFindings.length === 0 && !error) {
    return (
      <div className="klara-empty">
        <div className="klara-empty-icon">✓</div>
        <div className="klara-empty-text">{MESSAGES.NO_SUGGESTIONS}</div>
      </div>
    );
  }

  return (
    <div>
      {openFindings.length > 0 && (
        <div style={{ display: 'flex', gap: 6, padding: '8px 14px', borderBottom: '1px solid var(--border)' }}>
          {actionableFindings.length > 0 && (
            <button className="klara-btn klara-btn-primary klara-btn-sm" onClick={handleAcceptAll} disabled={loading}>
              Accept All
            </button>
          )}
          <button className="klara-btn klara-btn-ghost klara-btn-sm" onClick={handleRejectAll}>
            Reject All
          </button>
        </div>
      )}

      {error && (
        <div style={{ padding: '8px 14px', fontSize: 11, color: 'var(--danger)', background: 'var(--danger-bg)' }}>
          {error}
        </div>
      )}

      {openFindings.map((finding) => {
        const ef = effectiveFinding(finding);
        return (
          <SuggestionCard 
            key={finding.id} 
            finding={finding} 
            isResolved={false}
            onNavigate={() => handleNavigate(finding)}
            onAccept={() => ef.formatting_fix ? handleAcceptFormatting(ef) : handleAccept(ef)}
            onReject={() => handleReject(ef)}
            onComment={() => handleComment(ef)}
            onUndo={() => handleUndo(ef)}
            loading={loading}
            isEditing={editingId === finding.id}
            editValue={getReplacement(finding)}
            onEditStart={() => startEdit(finding)}
            onEditChange={(value: string) => setEditDraft(prev => ({ ...prev, [finding.id]: value }))}
            onEditSave={() => saveEdit()}
            onEditCancel={cancelEdit}
            replacementText={getReplacement(finding)}
          />
        );
      })}

      {resolvedFindings.length > 0 && (
        <div style={{ marginTop: '24px' }}>
          <div style={{ padding: '8px 14px', fontSize: 12, fontWeight: 'bold', color: 'var(--muted)', textTransform: 'uppercase' }}>
            {MESSAGES.RESOLVED_SUGGESTIONS} ({resolvedFindings.length})
          </div>
          {resolvedFindings.map((finding) => {
            const ef = effectiveFinding(finding);
            return (
              <SuggestionCard 
                key={finding.id} 
                finding={finding} 
                isResolved={true}
                isCommented={commentedIds.has(finding.id)}
                onNavigate={() => handleNavigate(finding)}
                onAccept={() => ef.formatting_fix ? handleAcceptFormatting(ef) : handleAccept(ef)}
                onReject={() => handleReject(ef)}
                onComment={() => handleComment(ef)}
                onUndo={() => handleUndo(ef)}
                loading={loading}
                isEditing={false}
                editValue={getReplacement(finding)}
                onEditStart={() => startEdit(finding)}
                onEditChange={(value: string) => setEditDraft(prev => ({ ...prev, [finding.id]: value }))}
                onEditSave={() => saveEdit()}
                onEditCancel={cancelEdit}
                replacementText={getReplacement(finding)}
              />
            );
          })}
        </div>
      )}
    </div>
  );
}
