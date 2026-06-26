import React, { useState, useCallback } from 'react';
import type { QCFinding } from '../types';
import { qcApi } from '../api/qc';
import { searchAndSelect, highlightRange, clearHighlights, replaceText } from '../word-context';

const SEVERITY_COLORS: Record<string, string> = {
  critical: 'var(--danger)',
  major: 'var(--warn)',
  minor: 'var(--info)',
  suggestion: 'var(--muted)',
};

const SEVERITY_LABELS: Record<string, string> = {
  critical: 'Critical',
  major: 'Major',
  minor: 'Minor',
  suggestion: 'Suggestion',
};

interface SuggestionsTabProps {
  findings: QCFinding[];
  onRefresh: () => void;
}

export function SuggestionsTab({ findings, onRefresh }: SuggestionsTabProps) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [acceptedIds, setAcceptedIds] = useState<Set<string>>(new Set());
  const [rejectedIds, setRejectedIds] = useState<Set<string>>(new Set());

  const openFindings = findings.filter(
    (f) => f.status === 'open' && !acceptedIds.has(f.id) && !rejectedIds.has(f.id)
  );

  const handleNavigate = useCallback(async (finding: QCFinding) => {
    await clearHighlights();
    const text = finding.original_text || finding.title;
    if (!text) return;

    const range = await searchAndSelect(text, 0);
    if (range) {
      const color = acceptedIds.has(finding.id)
        ? '#90ee90'
        : rejectedIds.has(finding.id)
        ? '#d3d3d3'
        : finding.severity === 'critical'
        ? '#ffcccc'
        : finding.severity === 'major'
        ? '#fff3cd'
        : '#ffffcc';
      await highlightRange(range, color);
    }
  }, [acceptedIds, rejectedIds]);

  const handleAccept = useCallback(async (finding: QCFinding) => {
    setLoading(true);
    setError('');
    try {
      const text = finding.original_text || finding.title;
      const replacement = finding.replacement_text || finding.suggested_fix || '';

      if (text && replacement) {
        await replaceText(text, replacement, 0);
      }

      await qcApi.resolveFinding(finding.id, {
        status: 'accepted',
        applied_text: replacement,
      });

      setAcceptedIds((prev) => new Set(prev).add(finding.id));
      setRejectedIds((prev) => {
        const next = new Set(prev);
        next.delete(finding.id);
        return next;
      });
      onRefresh();
    } catch (e: any) {
      setError(e.message || 'Failed to accept finding');
    } finally {
      setLoading(false);
    }
  }, [onRefresh]);

  const handleReject = useCallback(async (finding: QCFinding) => {
    try {
      await qcApi.resolveFinding(finding.id, {
        status: 'rejected',
      });
      setRejectedIds((prev) => new Set(prev).add(finding.id));
      setAcceptedIds((prev) => {
        const next = new Set(prev);
        next.delete(finding.id);
        return next;
      });
      onRefresh();
    } catch (e: any) {
      setError(e.message || 'Failed to reject finding');
    }
  }, [onRefresh]);

  const handleAcceptAll = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const pending = openFindings.filter((f) => f.replacement_text || f.suggested_fix);
      for (const finding of pending) {
        const text = finding.original_text || finding.title;
        const replacement = finding.replacement_text || finding.suggested_fix || '';
        if (text && replacement) {
          await replaceText(text, replacement, 0);
        }
        await qcApi.resolveFinding(finding.id, {
          status: 'accepted',
          applied_text: replacement,
        });
        setAcceptedIds((prev) => new Set(prev).add(finding.id));
      }
      onRefresh();
    } catch (e: any) {
      setError(e.message || 'Failed to accept all');
    } finally {
      setLoading(false);
    }
  }, [openFindings, onRefresh]);

  const handleRejectAll = useCallback(async () => {
    try {
      for (const finding of openFindings) {
        await qcApi.resolveFinding(finding.id, { status: 'rejected' });
        setRejectedIds((prev) => new Set(prev).add(finding.id));
      }
      onRefresh();
    } catch (e: any) {
      setError(e.message || 'Failed to reject all');
    }
  }, [openFindings, onRefresh]);

  if (loading) {
    return (
      <div className="klara-loading">
        <div className="klara-loading-spinner" />
        Processing...
      </div>
    );
  }

  if (openFindings.length === 0 && !error) {
    return (
      <div className="klara-empty">
        <div className="klara-empty-icon">✓</div>
        <div className="klara-empty-text">No pending suggestions</div>
      </div>
    );
  }

  return (
    <div>
      {openFindings.length > 0 && (
        <div style={{ display: 'flex', gap: 6, padding: '8px 14px', borderBottom: '1px solid var(--border)' }}>
          <button className="klara-btn klara-btn-primary klara-btn-sm" onClick={handleAcceptAll} disabled={loading}>
            Accept All
          </button>
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

      {openFindings.map((finding) => (
        <div
          key={finding.id}
          className="klara-card"
          style={{ cursor: 'pointer' }}
          onClick={() => handleNavigate(finding)}
        >
          <div className="klara-card-label">
            {finding.rule_name || finding.type} · {finding.severity}
          </div>
          <div className="klara-card-title">{finding.title}</div>
          {finding.description && (
            <div className="klara-card-desc">{finding.description}</div>
          )}
          {(finding.original_text || finding.replacement_text) && (
            <div className="klara-diff">
              {finding.original_text && (
                <div className="klara-diff-del">− {finding.original_text}</div>
              )}
              {finding.replacement_text && (
                <div className="klara-diff-add">+ {finding.replacement_text}</div>
              )}
              {finding.suggested_fix && !finding.replacement_text && (
                <div className="klara-diff-add">+ {finding.suggested_fix}</div>
              )}
            </div>
          )}
          <div className="klara-btn-group">
            <button
              className="klara-btn klara-btn-ghost klara-btn-sm"
              onClick={(e) => { e.stopPropagation(); handleReject(finding); }}
            >
              Reject
            </button>
            <button
              className="klara-btn klara-btn-primary klara-btn-sm"
              onClick={(e) => { e.stopPropagation(); handleAccept(finding); }}
            >
              Accept
            </button>
          </div>
        </div>
      ))}
    </div>
  );
}
