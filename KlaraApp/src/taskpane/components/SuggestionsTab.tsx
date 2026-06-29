import React, { useState, useCallback } from 'react';
import type { QCFinding } from '../types';
import type { TextReplacementResult } from '../word-context';
import { qcApi } from '../api/qc';
import { searchAndSelect, highlightRange, clearHighlights, replaceText, replaceTextInParagraph, selectParagraph, createKlaraComment, createKlaraCommentInParagraph, createKlaraCommentAtParagraph } from '../word-context';

const SEVERITY_COLORS: Record<string, string> = {
  critical: 'var(--danger)',
  major: 'var(--warn)',
  minor: 'var(--info)',
  suggestion: 'var(--muted)',
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
  const [commentedIds, setCommentedIds] = useState<Set<string>>(new Set());

  const openFindings = findings.filter(
    (f) => f.status === 'open' && !acceptedIds.has(f.id) && !rejectedIds.has(f.id) && !commentedIds.has(f.id)
  );

  const handleNavigate = useCallback(async (finding: QCFinding) => {
    await clearHighlights();

    const color = acceptedIds.has(finding.id)
      ? '#90ee90'
      : rejectedIds.has(finding.id)
      ? '#d3d3d3'
      : commentedIds.has(finding.id)
      ? '#e6f3ff'
      : finding.severity === 'critical'
      ? '#ffcccc'
      : finding.severity === 'major'
      ? '#fff3cd'
      : '#ffffcc';

    const text = finding.original_text || finding.title;
    if (text) {
      const range = await searchAndSelect(text, 0);
      if (range) {
        await highlightRange(range, color);
        return;
      }
    }

    // Fallback: If text search failed (e.g. truncated anchor text) or text is empty,
    // navigate directly to the paragraph index if it exists.
    if (finding.paragraph_index !== undefined && finding.paragraph_index !== null) {
      await selectParagraph(finding.paragraph_index, color);
    }
  }, [acceptedIds, rejectedIds]);

  const handleAccept = useCallback(async (finding: QCFinding) => {
    setLoading(true);
    setError('');
    try {
      const text = finding.original_text;
      const replacement = finding.replacement_text;

      if (!text || !replacement) {
        throw new Error('Cannot accept finding: missing original or replacement text');
      }

      console.log(`Accepting finding ${finding.id}: replacing "${text}" with "${replacement}"`);

      let result: TextReplacementResult;

      if (finding.paragraph_index !== undefined) {
        result = await replaceTextInParagraph(text, replacement, finding.paragraph_index);
      } else {
        result = await replaceText(text, replacement, 0);
      }

      console.log(`Replacement result:`, result);

      // Handle different scenarios
      if (result.success && result.applied) {
        // Text was successfully replaced
        console.log(`✅ Text replacement successful, updating finding status in backend...`);

        await qcApi.resolveFinding(finding.id, {
          status: 'accepted',
          applied_text: replacement,
        });

        console.log(`Finding ${finding.id} successfully accepted and applied`);

        setAcceptedIds((prev) => new Set(prev).add(finding.id));
        setRejectedIds((prev) => {
          const next = new Set(prev);
          next.delete(finding.id);
          return next;
        });
        setCommentedIds((prev) => {
          const next = new Set(prev);
          next.delete(finding.id);
          return next;
        });

        // Show success message temporarily
        setError('');
        onRefresh();

        // Scroll to show the change in the document
        const targetParagraph = result.actualParagraphIndex ?? finding.paragraph_index;
        if (targetParagraph !== undefined) {
          try {
            await selectParagraph(targetParagraph, '#90ee90');
          } catch (e) {
            console.warn('Could not highlight the changed paragraph:', e);
          }
        }

      } else if (result.success && !result.foundInDocument) {
        // Text was not found in document - auto-resolve as stale
        console.log(`ℹ️ Text "${text}" not found in document, auto-resolving as stale suggestion`);

        await qcApi.resolveFinding(finding.id, {
          status: 'accepted', // Still mark as accepted to remove it from list
          applied_text: replacement,
          resolution_notes: result.message,
          auto_resolved: true,
          not_found_in_document: true,
        });

        console.log(`Finding ${finding.id} auto-resolved (stale suggestion)`);

        setAcceptedIds((prev) => new Set(prev).add(finding.id));
        setRejectedIds((prev) => {
          const next = new Set(prev);
          next.delete(finding.id);
          return next;
        });
        setCommentedIds((prev) => {
          const next = new Set(prev);
          next.delete(finding.id);
          return next;
        });

        onRefresh();

      } else {
        // Something went wrong
        throw new Error(result.message || 'Unknown replacement error');
      }

    } catch (e: any) {
      console.error(`Failed to accept finding ${finding.id}:`, e);
      setError(`Failed to accept "${finding.title}": ${e.message || 'Unknown error'}`);
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
      setCommentedIds((prev) => {
        const next = new Set(prev);
        next.delete(finding.id);
        return next;
      });
      onRefresh();
    } catch (e: any) {
      setError(e.message || 'Failed to reject finding');
    }
  }, [onRefresh]);

  const handleComment = useCallback(async (finding: QCFinding) => {
    setLoading(true);
    setError('');
    try {
      const text = finding.original_text || finding.anchor_text;
      const commentText = finding.description || finding.title;

      console.log(`Adding Klara comment for finding ${finding.id}: "${commentText}"`);

      let result: { success: boolean; message: string };

      if (text && finding.paragraph_index !== undefined) {
        result = await createKlaraCommentInParagraph(text, `Klara AI: ${commentText}`, finding.paragraph_index, finding.id);
        if (!result.success && finding.paragraph_index !== undefined) {
          console.log(`Text search failed, falling back to paragraph-based comment`);
          result = await createKlaraCommentAtParagraph(finding.paragraph_index, `Klara AI: ${commentText}`, finding.id);
        }
      } else if (text) {
        result = await createKlaraComment(text, `Klara AI: ${commentText}`, finding.id);
      } else if (finding.paragraph_index !== undefined) {
        result = await createKlaraCommentAtParagraph(finding.paragraph_index, `Klara AI: ${commentText}`, finding.id);
      } else {
        throw new Error('Cannot add comment: missing text anchor and paragraph index');
      }

      console.log(`Comment result:`, result);

      if (result.success) {
        // Comment was successfully added
        console.log(`✅ Comment successfully added for finding ${finding.id}`);

        // Update the finding status in backend
        await qcApi.resolveFinding(finding.id, {
          status: 'accepted', // Mark as accepted to remove from list since comment was added
          resolution_notes: result.message,
        });

        console.log(`Finding ${finding.id} resolved with comment`);

        setCommentedIds((prev) => new Set(prev).add(finding.id));
        setAcceptedIds((prev) => new Set(prev).add(finding.id)); // Also add to accepted to remove from list
        setRejectedIds((prev) => {
          const next = new Set(prev);
          next.delete(finding.id);
          return next;
        });

        setError('');
        onRefresh();

        // Navigate to show the comment
        const targetParagraph = finding.paragraph_index;
        if (targetParagraph !== undefined) {
          try {
            await selectParagraph(targetParagraph, '#ffffcc');
          } catch (e) {
            console.warn('Could not highlight the commented paragraph:', e);
          }
        }
      } else {
        throw new Error(result.message || 'Comment creation failed');
      }

    } catch (e: any) {
      console.error(`Failed to add comment for finding ${finding.id}:`, e);
      setError(`Failed to add comment for "${finding.title}": ${e.message || 'Unknown error'}`);
    } finally {
      setLoading(false);
    }
  }, [onRefresh]);

  const handleAcceptAll = useCallback(async () => {
    setLoading(true);
    setError('');
    const appliedIds: string[] = [];
    const autoResolvedIds: string[] = [];
    const failedIds: string[] = [];
    const pending = openFindings.filter((f) => f.original_text && f.replacement_text);

    console.log(`Starting batch accept of ${pending.length} findings...`);

    for (const finding of pending) {
      try {
        const text = finding.original_text!;
        const replacement = finding.replacement_text!;

        console.log(`[${appliedIds.length + autoResolvedIds.length + 1}/${pending.length}] Accepting finding ${finding.id}: "${text}" -> "${replacement}"`);

        let result: TextReplacementResult;

        if (finding.paragraph_index !== undefined) {
          result = await replaceTextInParagraph(text, replacement, finding.paragraph_index);
        } else {
          result = await replaceText(text, replacement, 0);
        }

        if (result.success && result.applied) {
          await qcApi.resolveFinding(finding.id, {
            status: 'accepted',
            applied_text: replacement,
          });
          setAcceptedIds((prev) => new Set(prev).add(finding.id));
          setCommentedIds((prev) => {
            const next = new Set(prev);
            next.delete(finding.id);
            return next;
          });
          appliedIds.push(finding.id);
          console.log(`✅ Successfully accepted finding ${finding.id}`);
        } else if (result.success && !result.foundInDocument) {
          await qcApi.resolveFinding(finding.id, {
            status: 'accepted',
            applied_text: replacement,
            resolution_notes: result.message,
            auto_resolved: true,
            not_found_in_document: true,
          });
          setAcceptedIds((prev) => new Set(prev).add(finding.id));
          setCommentedIds((prev) => {
            const next = new Set(prev);
            next.delete(finding.id);
            return next;
          });
          autoResolvedIds.push(finding.id);
          console.log(`ℹ️ Auto-resolved finding ${finding.id} (not found in document)`);
        } else {
          failedIds.push(finding.id);
          console.warn(`⚠️ Failed to accept finding ${finding.id}: ${result.message}`);
        }
      } catch (e: any) {
        console.error(`Failed to accept finding ${finding.id}:`, e);
        failedIds.push(finding.id);
      }
    }

    onRefresh();

    // Show summary message
    const totalProcessed = appliedIds.length + autoResolvedIds.length;
    if (failedIds.length > 0) {
      console.warn(`Batch accept completed: ${appliedIds.length} applied, ${autoResolvedIds.length} auto-resolved, ${failedIds.length} failed`);
      setError(`${appliedIds.length} applied, ${autoResolvedIds.length} auto-resolved (stale), ${failedIds.length} failed`);
    } else if (autoResolvedIds.length > 0) {
      console.log(`Batch accept completed: ${appliedIds.length} applied, ${autoResolvedIds.length} auto-resolved`);
      setError(`${appliedIds.length} applied, ${autoResolvedIds.length} auto-resolved (stale suggestions)`);
    } else {
      console.log(`Batch accept completed: All ${appliedIds.length} findings successfully accepted`);
    }

    setLoading(false);
  }, [openFindings, onRefresh]);

  const handleRejectAll = useCallback(async () => {
    try {
      for (const finding of openFindings) {
        await qcApi.resolveFinding(finding.id, { status: 'rejected' });
        setRejectedIds((prev) => new Set(prev).add(finding.id));
        setCommentedIds((prev) => {
          const next = new Set(prev);
          next.delete(finding.id);
          return next;
        });
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
              className="klara-btn klara-btn-ghost klara-btn-sm"
              onClick={(e) => { e.stopPropagation(); handleComment(finding); }}
              disabled={loading}
            >
              Comment
            </button>
            <button
              className="klara-btn klara-btn-primary klara-btn-sm"
              onClick={(e) => { e.stopPropagation(); handleAccept(finding); }}
              disabled={loading}
            >
              Accept
            </button>
          </div>
        </div>
      ))}
    </div>
  );
}
