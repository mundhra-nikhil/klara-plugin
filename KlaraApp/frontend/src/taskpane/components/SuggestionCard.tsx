import React from 'react';
import type { QCFinding } from '../types';
import { isActionableFinding } from '../hooks/useFindingsActions';
import { FINDING_STATUS, RULE_NAMES, REGEX_PATTERNS, MESSAGES } from '../constants';

export interface SuggestionCardProps {
  finding: QCFinding;
  isResolved: boolean;
  isCommented?: boolean;
  onNavigate: () => void;
  onAccept: () => void;
  onReject: () => void;
  onComment: () => void;
  onUndo: () => void;
  loading: boolean;
  isEditing: boolean;
  editValue: string;
  onEditStart: () => void;
  onEditChange: (value: string) => void;
  onEditSave: () => void;
  onEditCancel: () => void;
  replacementText: string;
}

export function SuggestionCard({ 
  finding, 
  isResolved, 
  isCommented,
  onNavigate, 
  onAccept, 
  onReject, 
  onComment, 
  onUndo, 
  loading,
  isEditing,
  editValue,
  onEditStart,
  onEditChange,
  onEditSave,
  onEditCancel,
  replacementText
}: SuggestionCardProps) {
  const isRestrictedLocation = (finding.title + " " + (finding.description || "") + " " + (finding.location || "")).toLowerCase().match(REGEX_PATTERNS.RESTRICTED_COMMENT_ZONES);
  const isFontConsistency = finding.rule_name?.toUpperCase().includes(RULE_NAMES.FONT_CONSISTENCY);
  const isFontSizeFix = isFontConsistency && editValue?.toLowerCase().includes('font size');
  const fontMatch = editValue?.match(REGEX_PATTERNS.NUMBERS_ONLY);
  const fontSizeNum = fontMatch ? fontMatch[1] : '';
  
  return (
    <div
      className={`klara-card ${isResolved && !isCommented ? 'klara-card-resolved' : ''}`}
      style={{ cursor: 'pointer', opacity: isResolved && !isCommented ? 0.7 : 1 }}
      onClick={isEditing ? undefined : onNavigate}
    >
      <div className="klara-card-label">
        {finding.rule_name || finding.type} · {finding.severity}
        {isResolved && (
          <span style={{ marginLeft: 8, color: 'var(--success)', fontWeight: 'bold' }}>
            {finding.status === FINDING_STATUS.ACCEPTED ? '✓ Accepted' : finding.status === FINDING_STATUS.REJECTED ? '✗ Rejected' : '✓ Commented'}
          </span>
        )}
      </div>
      <div className="klara-card-title">{finding.title}</div>
      {finding.description && (
        <div className="klara-card-desc">{finding.description}</div>
      )}
      {(finding.original_text || replacementText) && (
        <div className="klara-diff">
          {finding.original_text && (
            <div className="klara-diff-del">− {finding.original_text}</div>
          )}
          {isEditing ? (
            isFontSizeFix ? (
              <div style={{ marginTop: 4, display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span style={{ fontSize: '13px', color: 'var(--fg)' }}>Set font size to:</span>
                <input
                  type="number"
                  className="klara-input"
                  style={{ width: '60px', padding: '4px 8px', fontSize: '13px' }}
                  min="1"
                  max="72"
                  value={fontSizeNum}
                  onChange={(e) => {
                    const val = e.target.value;
                    const suffix = editValue.toLowerCase().includes('footnote') ? 'footnote font size' : 'font size';
                    onEditChange(`Set the ${suffix} to ${val}pt.`);
                  }}
                  onClick={(e) => e.stopPropagation()}
                />
                <span style={{ fontSize: '13px', color: 'var(--fg)' }}>pt.</span>
              </div>
            ) : (
              <div style={{ marginTop: 4 }}>
                <textarea
                  className="klara-edit-textarea"
                  value={editValue}
                  onChange={(e) => onEditChange(e.target.value)}
                  onClick={(e) => e.stopPropagation()}
                  autoFocus
                  onFocus={(e) => {
                    const val = e.target.value;
                    e.target.value = '';
                    e.target.value = val;
                  }}
                />
              </div>
            )
          ) : (
            replacementText && (
              <div className="klara-diff-add">+ {replacementText}</div>
            )
          )}
        </div>
      )}
      <div className="klara-btn-group">
        {isEditing ? (
          <>
            <button
              className="klara-btn klara-btn-ghost klara-btn-sm"
              onClick={(e) => { e.stopPropagation(); onEditCancel(); }}
              disabled={loading}
            >
              Cancel
            </button>
            <button
              className="klara-btn klara-btn-primary klara-btn-sm"
              onClick={(e) => { e.stopPropagation(); onEditSave(); }}
              disabled={loading}
            >
              Save
            </button>
          </>
        ) : isResolved ? (
          <>
            <button
              className="klara-btn klara-btn-ghost klara-btn-sm"
              onClick={(e) => { e.stopPropagation(); onUndo(); }}
              disabled={loading}
            >
              Undo
            </button>
            {isCommented && (
              <>
                <button
                  className="klara-btn klara-btn-ghost klara-btn-sm"
                  onClick={(e) => { e.stopPropagation(); onReject(); }}
                  disabled={loading}
                >
                  Reject
                </button>
                <button
                  className="klara-btn klara-btn-primary klara-btn-sm"
                  onClick={(e) => { e.stopPropagation(); onAccept(); }}
                  disabled={loading}
                >
                  Accept
                </button>
              </>
            )}
          </>
        ) : (
          <>
            {!!replacementText && (
              <button
                className="klara-btn klara-btn-ghost klara-btn-sm"
                onClick={(e) => { e.stopPropagation(); onEditStart(); }}
                disabled={loading}
              >
                Edit
              </button>
            )}
            <button
              className="klara-btn klara-btn-ghost klara-btn-sm"
              onClick={(e) => { e.stopPropagation(); onReject(); }}
              disabled={loading}
            >
              Reject
            </button>
            <button
              className="klara-btn klara-btn-ghost klara-btn-sm"
              onClick={(e) => { e.stopPropagation(); onComment(); }}
              disabled={loading || !!isRestrictedLocation}
              title={isRestrictedLocation ? MESSAGES.RESTRICTED_COMMENT : undefined}
            >
              Comment
            </button>
            {isActionableFinding(finding) && (
              <button
                className="klara-btn klara-btn-primary klara-btn-sm"
                onClick={(e) => { e.stopPropagation(); onAccept(); }}
                disabled={loading}
              >
                Accept
              </button>
            )}
          </>
        )}
      </div>
    </div>
  );
}
