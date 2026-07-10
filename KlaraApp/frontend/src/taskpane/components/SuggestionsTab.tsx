import React, { useState, useCallback } from 'react';
import type { QCFinding } from '../types';
import type { TextReplacementResult, FormattingResult } from '../word-context';
import { useQueryClient } from '@tanstack/react-query';
import { qcApi } from '../api/qc';
import { searchAndSelect, highlightRange, clearHighlights, replaceText, replaceTextInParagraph, selectParagraph, createKlaraComment, createKlaraCommentInParagraph, createKlaraCommentAtParagraph, applyParagraphFormatting, searchAndApplyFormatting, createSimulatedTrackedChange, createSimulatedTrackedChangeInParagraph, acceptSimulatedTrackedChange, rejectSimulatedTrackedChange, undoSimulatedTrackedChange, undoDirectReplacement } from '../word-context';

const SEVERITY_COLORS: Record<string, string> = {
  critical: 'var(--danger)',
  major: 'var(--warn)',
  minor: 'var(--info)',
  suggestion: 'var(--muted)',
};

const isActionableFinding = (f: QCFinding): boolean => {
  // Text replacement findings are actionable
  if (f.original_text && f.replacement_text && f.original_text !== f.replacement_text) {
    return true;
  }
  // Formatting fix findings are actionable
  if (f.formatting_fix) {
    return true;
  }
  return false;
};

interface SuggestionsTabProps {
  findings: QCFinding[];
  docId: string | null;
}

export function SuggestionsTab({ findings, docId }: SuggestionsTabProps) {
  const queryClient = useQueryClient();

  const onRefresh = useCallback(() => {
    queryClient.invalidateQueries({ queryKey: ['findings', docId] });
  }, [queryClient, docId]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [acceptedIds, setAcceptedIds] = useState<Set<string>>(new Set());
  const [rejectedIds, setRejectedIds] = useState<Set<string>>(new Set());
  const [commentedIds, setCommentedIds] = useState<Set<string>>(new Set());

  const openFindings = findings.filter(
    (f) => f.status.toLowerCase() === 'open' && !acceptedIds.has(f.id) && !rejectedIds.has(f.id) && !commentedIds.has(f.id)
  );

  const resolvedFindings = findings.filter(
    (f) => f.status.toLowerCase() !== 'open' || acceptedIds.has(f.id) || rejectedIds.has(f.id) || commentedIds.has(f.id)
  );

  const actionableFindings = openFindings.filter(isActionableFinding);

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

      // Handle accepting a simulated tracked change
      if (commentedIds.has(finding.id)) {
        console.log(`Accepting simulated tracked change ${finding.id}`);
        const acceptResult = await acceptSimulatedTrackedChange(finding.id, replacement);
        if (!acceptResult.success) {
          throw new Error(acceptResult.message);
        }

        await qcApi.resolveFinding(finding.id, {
          status: 'accepted',
          applied_text: replacement,
        });

        setAcceptedIds((prev) => new Set(prev).add(finding.id));
        setRejectedIds((prev) => { const next = new Set(prev); next.delete(finding.id); return next; });
        setCommentedIds((prev) => { const next = new Set(prev); next.delete(finding.id); return next; });
        
        setError('');
        onRefresh();
        return;
      }

      console.log(`Starting text replacement for finding ${finding.id}: "${text}" -> "${replacement}"`);

      let result: TextReplacementResult;

      // Try paragraph-specific replacement first if we have the index
      if (finding.paragraph_index !== undefined && finding.paragraph_index !== null) {
        console.log(`Trying paragraph-specific replacement at index ${finding.paragraph_index}`);
        result = await replaceTextInParagraph(text, replacement, finding.paragraph_index);
      } else {
        console.log(`No paragraph index, doing global search and replace`);
        result = await replaceText(text, replacement, 0); // Always use instance 0 for now
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
            await selectParagraph(targetParagraph);
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

  const handleAcceptFormatting = useCallback(async (finding: QCFinding) => {
    setLoading(true);
    setError('');
    try {
      if (!finding.formatting_fix) {
        throw new Error('Cannot accept formatting: missing formatting fix definition');
      }

      console.log(`Accepting formatting fix ${finding.id}:`, finding.formatting_fix);

      let result: FormattingResult;

      // Use paragraph index if available, otherwise search for the text
      if (finding.paragraph_index !== undefined && finding.paragraph_index !== null) {
        result = await applyParagraphFormatting(finding.paragraph_index, finding.formatting_fix);
      } else if (finding.original_text || finding.anchor_text) {
        const searchText = finding.original_text || finding.anchor_text;
        result = await searchAndApplyFormatting(searchText!, finding.formatting_fix);
      } else {
        throw new Error('Cannot apply formatting: missing paragraph index and search text');
      }

      console.log(`Formatting result:`, result);

      // Handle the result
      if (result.success && result.applied) {
        // Formatting was successfully applied
        console.log(`✅ Formatting successfully applied, updating finding status in backend...`);

        await qcApi.resolveFinding(finding.id, {
          status: 'accepted',
          resolution_notes: result.message,
        });

        console.log(`Finding ${finding.id} successfully accepted and formatting applied`);

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
        const targetParagraph = result.paragraphIndex ?? finding.paragraph_index;
        if (targetParagraph !== undefined) {
          try {
            await selectParagraph(targetParagraph);
          } catch (e) {
            console.warn('Could not highlight the formatted paragraph:', e);
          }
        }

      } else {
        // Something went wrong
        throw new Error(result.message || 'Unknown formatting error');
      }

    } catch (e: any) {
      console.error(`Failed to accept formatting ${finding.id}:`, e);
      setError(`Failed to accept formatting for "${finding.title}": ${e.message || 'Unknown error'}`);
    } finally {
      setLoading(false);
    }
  }, [onRefresh]);

  const handleReject = useCallback(async (finding: QCFinding) => {
    try {
      if (commentedIds.has(finding.id)) {
         const result = await rejectSimulatedTrackedChange(finding.id, finding.original_text || "");
         if (!result.success) throw new Error(result.message);
      }
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

      if (finding.replacement_text && finding.original_text) {
        if (finding.paragraph_index !== undefined && finding.paragraph_index !== null) {
          result = await createSimulatedTrackedChangeInParagraph(finding.original_text, finding.replacement_text, commentText, finding.paragraph_index, finding.id);
        } else {
          result = await createSimulatedTrackedChange(finding.original_text, finding.replacement_text, commentText, finding.id);
        }
      } else {
        if (text && finding.paragraph_index !== undefined && finding.paragraph_index !== null) {
          result = await createKlaraCommentInParagraph(text, `Klara AI: ${commentText}`, finding.paragraph_index, finding.id);
          if (!result.success && finding.paragraph_index !== undefined && finding.paragraph_index !== null) {
            console.log(`Text search failed, falling back to paragraph-based comment`);
            result = await createKlaraCommentAtParagraph(finding.paragraph_index, `Klara AI: ${commentText}`, finding.id);
          }
        } else if (text) {
          result = await createKlaraComment(text, `Klara AI: ${commentText}`, finding.id);
        } else if (finding.paragraph_index !== undefined && finding.paragraph_index !== null) {
          result = await createKlaraCommentAtParagraph(finding.paragraph_index, `Klara AI: ${commentText}`, finding.id);
        } else {
          throw new Error('Cannot add comment: missing text anchor and paragraph index');
        }
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
        if (!finding.replacement_text) {
          setAcceptedIds((prev) => new Set(prev).add(finding.id)); // Only auto-accept standard comments
        }
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
            await selectParagraph(targetParagraph);
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

  const handleUndo = useCallback(async (finding: QCFinding) => {
    setLoading(true);
    setError('');
    try {
      if (acceptedIds.has(finding.id)) {
        if (finding.replacement_text && finding.original_text) {
          await undoDirectReplacement(finding.replacement_text, finding.original_text, finding.paragraph_index);
        }
      } else if (commentedIds.has(finding.id)) {
        if (finding.original_text) {
          await undoSimulatedTrackedChange(finding.id, finding.original_text);
        }
      }

      await qcApi.resolveFinding(finding.id, {
        status: 'open',
      });

      setAcceptedIds((prev) => { const next = new Set(prev); next.delete(finding.id); return next; });
      setRejectedIds((prev) => { const next = new Set(prev); next.delete(finding.id); return next; });
      setCommentedIds((prev) => { const next = new Set(prev); next.delete(finding.id); return next; });
      
      onRefresh();
    } catch (e: any) {
      console.error(`Failed to undo finding ${finding.id}:`, e);
      setError(`Failed to undo for "${finding.title}": ${e.message || 'Unknown error'}`);
    } finally {
      setLoading(false);
    }
  }, [acceptedIds, rejectedIds, commentedIds, onRefresh]);

  const handleAcceptAll = useCallback(async () => {
    setLoading(true);
    setError('');
    const appliedIds: string[] = [];
    const autoResolvedIds: string[] = [];
    const formattingAppliedIds: string[] = [];
    const failedIds: string[] = [];
    const pending = actionableFindings;

    console.log(`Starting batch accept of ${pending.length} findings...`);

    for (const finding of pending) {
      try {
        // Handle formatting fixes
        if (finding.formatting_fix) {
          console.log(`[${appliedIds.length + autoResolvedIds.length + formattingAppliedIds.length + 1}/${pending.length}] Applying formatting fix ${finding.id}`);

          let result: FormattingResult;

          if (finding.paragraph_index !== undefined && finding.paragraph_index !== null) {
            result = await applyParagraphFormatting(finding.paragraph_index, finding.formatting_fix);
          } else if (finding.original_text || finding.anchor_text) {
            const searchText = finding.original_text || finding.anchor_text;
            result = await searchAndApplyFormatting(searchText!, finding.formatting_fix);
          } else {
            console.warn(`⚠️ Cannot apply formatting ${finding.id}: missing location info`);
            failedIds.push(finding.id);
            continue;
          }

          if (result.success && result.applied) {
            await qcApi.resolveFinding(finding.id, {
              status: 'accepted',
              resolution_notes: result.message,
            });
            setAcceptedIds((prev) => new Set(prev).add(finding.id));
            setCommentedIds((prev) => {
              const next = new Set(prev);
              next.delete(finding.id);
              return next;
            });
            formattingAppliedIds.push(finding.id);
            console.log(`✅ Successfully applied formatting for finding ${finding.id}`);
          } else {
            failedIds.push(finding.id);
            console.warn(`⚠️ Failed to apply formatting ${finding.id}: ${result.message}`);
          }
          continue;
        }

        // Handle text replacements
        const text = finding.original_text!;
        const replacement = finding.replacement_text!;

        if (!text || !replacement) {
          console.warn(`⚠️ Skipping finding ${finding.id}: missing text or replacement`);
          failedIds.push(finding.id);
          continue;
        }

        console.log(`[${appliedIds.length + autoResolvedIds.length + formattingAppliedIds.length + 1}/${pending.length}] Accepting finding ${finding.id}: "${text}" -> "${replacement}"`);

        let result: TextReplacementResult;

        if (finding.paragraph_index !== undefined && finding.paragraph_index !== null) {
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
    const totalProcessed = appliedIds.length + autoResolvedIds.length + formattingAppliedIds.length;
    if (failedIds.length > 0) {
      console.warn(`Batch accept completed: ${appliedIds.length} applied, ${autoResolvedIds.length} auto-resolved, ${formattingAppliedIds.length} formatting applied, ${failedIds.length} failed`);
      setError(`${appliedIds.length} applied, ${autoResolvedIds.length} auto-resolved, ${formattingAppliedIds.length} formatting, ${failedIds.length} failed`);
    } else if (autoResolvedIds.length > 0) {
      console.log(`Batch accept completed: ${appliedIds.length} applied, ${formattingAppliedIds.length} formatting applied, ${autoResolvedIds.length} auto-resolved`);
      setError(`${appliedIds.length} applied, ${formattingAppliedIds.length} formatting, ${autoResolvedIds.length} auto-resolved (stale suggestions)`);
    } else {
      console.log(`Batch accept completed: All ${totalProcessed} findings successfully accepted (${formattingAppliedIds.length} formatting, ${appliedIds.length} text replacements)`);
    }

    setLoading(false);
  }, [actionableFindings, onRefresh]);

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

      {openFindings.map((finding) => (
        <SuggestionCard 
          key={finding.id} 
          finding={finding} 
          isResolved={false}
          onNavigate={() => handleNavigate(finding)}
          onAccept={() => finding.formatting_fix ? handleAcceptFormatting(finding) : handleAccept(finding)}
          onReject={() => handleReject(finding)}
          onComment={() => handleComment(finding)}
          onUndo={() => handleUndo(finding)}
          loading={loading}
        />
      ))}

      {resolvedFindings.length > 0 && (
        <div style={{ marginTop: '24px' }}>
          <div style={{ padding: '8px 14px', fontSize: 12, fontWeight: 'bold', color: 'var(--muted)', textTransform: 'uppercase' }}>
            Resolved Suggestions ({resolvedFindings.length})
          </div>
          {resolvedFindings.map((finding) => (
            <SuggestionCard 
              key={finding.id} 
              finding={finding} 
              isResolved={true}
              isCommented={commentedIds.has(finding.id)}
              onNavigate={() => handleNavigate(finding)}
              onAccept={() => finding.formatting_fix ? handleAcceptFormatting(finding) : handleAccept(finding)}
              onReject={() => handleReject(finding)}
              onComment={() => handleComment(finding)}
              onUndo={() => handleUndo(finding)}
              loading={loading}
            />
          ))}
        </div>
      )}
    </div>
  );
}

// Add a helper component to simplify rendering
function SuggestionCard({ 
  finding, 
  isResolved, 
  isCommented,
  onNavigate, 
  onAccept, 
  onReject, 
  onComment, 
  onUndo, 
  loading 
}: any) {
  return (
    <div
      className={`klara-card ${isResolved && !isCommented ? 'klara-card-resolved' : ''}`}
      style={{ cursor: 'pointer', opacity: isResolved && !isCommented ? 0.7 : 1 }}
      onClick={onNavigate}
    >
      <div className="klara-card-label">
        {finding.rule_name || finding.type} · {finding.severity}
        {isResolved && (
          <span style={{ marginLeft: 8, color: 'var(--success)', fontWeight: 'bold' }}>
            {finding.status === 'accepted' ? '✓ Accepted' : finding.status === 'rejected' ? '✗ Rejected' : '✓ Commented'}
          </span>
        )}
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
        {isResolved ? (
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
            <button
              className="klara-btn klara-btn-ghost klara-btn-sm"
              onClick={(e) => { e.stopPropagation(); onReject(); }}
            >
              Reject
            </button>
            <button
              className="klara-btn klara-btn-ghost klara-btn-sm"
              onClick={(e) => { e.stopPropagation(); onComment(); }}
              disabled={loading}
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
