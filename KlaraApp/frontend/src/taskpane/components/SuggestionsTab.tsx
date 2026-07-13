import React, { useState, useCallback } from 'react';
import type { QCFinding } from '../types';
import { useFindingsActions } from '../hooks/useFindingsActions';
import { SuggestionCard } from './SuggestionCard';
import { FINDING_TYPES, MESSAGES, RULE_NAMES, REGEX_PATTERNS } from '../constants';

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
    const replacement = getReplacement(f) || f.replacement_text;
    let formatting_fix = f.formatting_fix;
    
    // Inject formatting_fix for Font Consistency cards that only have text replacements
    const isFontConsistency = f.rule_name?.toUpperCase().includes(RULE_NAMES.FONT_CONSISTENCY);
    if (isFontConsistency && replacement && !formatting_fix) {
       const match = replacement.match(REGEX_PATTERNS.NUMBERS_ONLY);
       if (match) {
         formatting_fix = {
           type: FINDING_TYPES.FONT,
           fontSize: parseInt(match[1], 10)
         };
       }
    }

    return {
      ...f,
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
