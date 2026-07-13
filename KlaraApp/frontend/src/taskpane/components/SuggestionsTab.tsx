import React, { useState, useCallback } from 'react';
import type { QCFinding } from '../types';
import type { TextReplacementResult, FormattingResult } from '../word';
import { useQueryClient } from '@tanstack/react-query';
import { qcApi } from '../api/qc';
import { searchAndSelect, highlightRange, clearHighlights, replaceText, replaceTextInParagraph, selectParagraph, createKlaraComment, createKlaraCommentInParagraph, createKlaraCommentAtParagraph, applyParagraphFormatting, searchAndApplyFormatting, applyGlobalFormatting, createSimulatedTrackedChange, createSimulatedTrackedChangeInParagraph, acceptSimulatedTrackedChange, rejectSimulatedTrackedChange, undoSimulatedTrackedChange, undoDirectReplacement, undoFormatting } from '../word';

const SEVERITY_COLORS: Record<string, string> = {
  critical: 'var(--danger)',
  major: 'var(--warn)',
  minor: 'var(--info)',
  suggestion: 'var(--muted)',
};

const isActionableFinding = (_f: QCFinding): boolean => {
  // All findings can be "Accepted" by the user to mark them as resolved,
  // even if they require manual formatting fixes or have no automated text replacement.
  return true;
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

  const [editingId, setEditingId] = useState<string | null>(null);
  const [editDraft, setEditDraft] = useState<Record<string, string>>({});
  const [localUndoStates, setLocalUndoStates] = useState<Record<string, any>>({});

  const getReplacement = useCallback((f: QCFinding) => {
    return editDraft[f.id] ?? f.replacement_text ?? f.suggested_fix ?? '';
  }, [editDraft]);

  const effectiveFinding = useCallback((f: QCFinding): QCFinding => {
    const replacement = getReplacement(f) || f.replacement_text;
    let formatting_fix = f.formatting_fix;
    
    // Inject formatting_fix for Font Consistency cards that only have text replacements
    const isFontConsistency = f.rule_name?.toUpperCase().includes('FONT CONSISTENCY');
    if (isFontConsistency && replacement && !formatting_fix) {
       const match = replacement.match(/(\d+)/);
       if (match) {
         formatting_fix = {
           type: "font",
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

  const clearEdit = useCallback((id: string) => {
    setEditDraft((prev) => {
      const n = { ...prev };
      delete n[id];
      return n;
    });
  }, []);

  const openFindings = findings.filter(
    (f) => f.status.toLowerCase() === 'open' && !acceptedIds.has(f.id) && !rejectedIds.has(f.id) && !commentedIds.has(f.id)
  );

  const resolvedFindings = findings.filter(
    (f) => f.status.toLowerCase() !== 'open' || acceptedIds.has(f.id) || rejectedIds.has(f.id) || commentedIds.has(f.id)
  );

  const actionableFindings = openFindings.filter(isActionableFinding);

  const handleNavigate = useCallback(async (finding: QCFinding) => {
    const text = finding.original_text || finding.anchor_text;
    if (text) {
      const result = await searchAndSelect(text, 0);
      if (result && result.range) {
        if (result.error) {
          setError(`Word API blocked precise selection (${result.error}). Highlighted containing paragraphs instead.`);
          setTimeout(() => setError(''), 5000); // Clear after 5 seconds
        }
        return;
      } else if (result && result.error) {
        setError(`Word API blocked selection: ${result.error}`);
        setTimeout(() => setError(''), 5000);
        
        // If we caught an error but couldn't even safely select the paragraphs,
        // we should still return so we don't fall back to the single-line highlight below.
        // Actually, if we return here, nothing gets highlighted if safe selection failed.
        // But if we don't return, it selects just the first line.
        // Let's at least let it select the first line but keep the error visible.
      }
    }

    if (finding.title.toLowerCase().includes("footnote") || finding.location?.toLowerCase().includes("footnote")) {
       return; // Don't mistakenly navigate to a random body paragraph
    }

    // Fallback: If text search failed (e.g. truncated anchor text) or text is empty,
    // navigate directly to the paragraph index if it exists.
    if (finding.paragraph_index !== undefined && finding.paragraph_index !== null) {
      await selectParagraph(finding.paragraph_index);
    }
  }, [acceptedIds, rejectedIds]);

  const handleAccept = useCallback(async (finding: QCFinding) => {
    setLoading(true);
    setError('');
    try {
      const text = finding.original_text;
      const replacement = finding.replacement_text;

      // Handle accepting a simulated tracked change
      if (commentedIds.has(finding.id)) {
        console.log(`Accepting simulated tracked change ${finding.id}`);
        // If there is no replacement, we just mark it accepted (since the comment was purely informational)
        if (text && replacement && text !== replacement) {
          const acceptResult = await acceptSimulatedTrackedChange(finding.id, replacement);
          if (!acceptResult.success) {
            throw new Error(acceptResult.message);
          }
        }

        await qcApi.resolveFinding(finding.id, {
          status: 'accepted',
          applied_text: replacement || '',
        });

        setAcceptedIds((prev) => new Set(prev).add(finding.id));
        setRejectedIds((prev) => { const next = new Set(prev); next.delete(finding.id); return next; });
        setCommentedIds((prev) => { const next = new Set(prev); next.delete(finding.id); return next; });
        
        setError('');
        clearEdit(finding.id);
        onRefresh();
        return;
      }

      if (!text || replacement === undefined || replacement === null || text === replacement) {
        // If there's no text replacement to do (either missing text or identical),
        // just mark it as accepted in the backend without modifying the document.
        console.log(`Accepting finding ${finding.id} without text modification`);
        await qcApi.resolveFinding(finding.id, {
          status: 'accepted',
          applied_text: replacement || '',
        });

        setAcceptedIds((prev) => new Set(prev).add(finding.id));
        setRejectedIds((prev) => { const next = new Set(prev); next.delete(finding.id); return next; });
        setCommentedIds((prev) => { const next = new Set(prev); next.delete(finding.id); return next; });
        
        setError('');
        clearEdit(finding.id);
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
        clearEdit(finding.id);
        onRefresh();

        // Navigate to show the change in the document
        const targetParagraph = result.actualParagraphIndex ?? finding.paragraph_index;
        const isRestrictedLocation = (finding.title + " " + (finding.description || "") + " " + (finding.location || "")).toLowerCase().match(/footnote|footer|header/);
        
        if (targetParagraph !== undefined && !isRestrictedLocation) {
          try {
            await selectParagraph(targetParagraph);
          } catch (e) {
            console.warn('Could not highlight the replaced paragraph:', e);
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

        clearEdit(finding.id);
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
  }, [onRefresh, clearEdit]);

  const handleAcceptFormatting = useCallback(async (finding: QCFinding) => {
    setLoading(true);
    setError('');
    try {
      if (!finding.formatting_fix) {
        throw new Error('Cannot accept formatting: missing formatting fix definition');
      }

      console.log(`Accepting formatting fix ${finding.id}:`, finding.formatting_fix);

      let result: FormattingResult;

      const searchText = finding.original_text || finding.anchor_text;

      const findingContextText = (finding.title + " " + (finding.description || "")).toLowerCase();
      
      if (findingContextText.includes("footnote")) {
        // If the finding is specifically about footnotes, apply formatting globally to all footnotes.
        // We do this first because searching for the anchor text might find the footnote reference 
        // in the main document body, causing the formatting to be incorrectly applied to the body paragraph.
        result = await applyGlobalFormatting(finding.formatting_fix, findingContextText);
      } else if (finding.paragraph_index !== undefined && finding.paragraph_index !== null) {
        result = await applyParagraphFormatting(finding.paragraph_index, finding.formatting_fix, searchText);
      } else if (searchText) {
        result = await searchAndApplyFormatting(searchText, finding.formatting_fix);
      } else {
        result = await applyGlobalFormatting(finding.formatting_fix, findingContextText);
      }

      console.log(`Formatting result:`, result);

      if (result.success && result.applied) {
        // Formatting was successfully applied
        console.log(`✅ Formatting successfully applied, updating finding status in backend...`);

        await qcApi.resolveFinding(finding.id, {
          status: 'accepted',
          resolution_notes: JSON.stringify({
            message: result.message,
            undo_state: result.previous_state
          }),
        });
        
        setLocalUndoStates(prev => ({ ...prev, [finding.id]: result.previous_state }));

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
        clearEdit(finding.id);
        onRefresh();

        // Scroll to show the change in the document
        const targetParagraph = result.paragraphIndex ?? finding.paragraph_index;
        const isRestrictedLocation = (finding.title + " " + (finding.description || "") + " " + (finding.location || "")).toLowerCase().match(/footnote|footer|header/);
        
        if (targetParagraph !== undefined && !isRestrictedLocation) {
          try {
            await selectParagraph(targetParagraph);
          } catch (e) {
            console.warn('Could not highlight the formatted paragraph:', e);
          }
        }

      } else if (result.success && result.foundInDocument === false) {
        console.log(`ℹ️ Location not found for formatting fix, auto-resolving as stale suggestion`);

        await qcApi.resolveFinding(finding.id, {
          status: 'accepted',
          resolution_notes: result.message,
          auto_resolved: true,
          not_found_in_document: true,
        });

        console.log(`Finding ${finding.id} auto-resolved (stale formatting suggestion)`);

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

        setError('');
        clearEdit(finding.id);
        onRefresh();

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
  }, [onRefresh, clearEdit]);

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
      clearEdit(finding.id);
      onRefresh();
    } catch (e: any) {
      setError(e.message || 'Failed to reject finding');
    }
  }, [onRefresh, clearEdit]);

  const handleComment = useCallback(async (finding: QCFinding) => {
    setLoading(true);
    setError('');
    try {
      const text = finding.original_text || finding.anchor_text;
      const commentText = finding.description || finding.title;

      console.log(`Adding Klara comment for finding ${finding.id}: "${commentText}"`);

      let result: { success: boolean; message: string; foundInDocument?: boolean };

      if (finding.replacement_text && finding.original_text && finding.replacement_text !== finding.original_text) {
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
        clearEdit(finding.id);
        onRefresh();

        // Navigate to show the comment
        const targetParagraph = finding.paragraph_index;
        const isRestrictedLocation = (finding.title + " " + (finding.description || "") + " " + (finding.location || "")).toLowerCase().match(/footnote|footer|header/);
        
        if (targetParagraph !== undefined && !isRestrictedLocation) {
          try {
            await selectParagraph(targetParagraph);
          } catch (e) {
            console.warn('Could not highlight the commented paragraph:', e);
          }
        }
      } else if (result.success === false && result.foundInDocument === false) {
        console.log(`ℹ️ Text not found for comment, auto-resolving as stale suggestion`);

        await qcApi.resolveFinding(finding.id, {
          status: 'accepted',
          resolution_notes: result.message,
          auto_resolved: true,
          not_found_in_document: true,
        });

        console.log(`Finding ${finding.id} auto-resolved (stale comment suggestion)`);

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

        setError('');
        clearEdit(finding.id);
        onRefresh();
      } else {
        throw new Error(result.message || 'Comment creation failed');
      }

    } catch (e: any) {
      console.error(`Failed to add comment for finding ${finding.id}:`, e);
      setError(`Failed to add comment for "${finding.title}": ${e.message || 'Unknown error'}`);
    } finally {
      setLoading(false);
    }
  }, [onRefresh, clearEdit]);

  const handleUndo = useCallback(async (finding: QCFinding) => {
    setLoading(true);
    setError('');
    try {
      const isAccepted = finding.status === 'accepted' || acceptedIds.has(finding.id);
      const isCommented = finding.status === 'deferred' || commentedIds.has(finding.id);

      if (isAccepted) {
        if (finding.replacement_text && finding.original_text) {
          await undoDirectReplacement(finding.replacement_text, finding.original_text, finding.paragraph_index);
        } else if (finding.formatting_fix) {
          let undoState = localUndoStates[finding.id];
          if (!undoState && finding.resolution_notes) {
            try {
              const parsedNotes = JSON.parse(finding.resolution_notes);
              undoState = parsedNotes.undo_state;
            } catch (e) {
              console.error("Failed to parse resolution_notes for undo:", e);
            }
          }
          if (undoState) {
            await undoFormatting(undoState);
          }
        }
      } else if (isCommented) {
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
      
      clearEdit(finding.id);
      onRefresh();
    } catch (e: any) {
      console.error(`Failed to undo finding ${finding.id}:`, e);
      setError(`Failed to undo for "${finding.title}": ${e.message || 'Unknown error'}`);
    } finally {
      setLoading(false);
    }
  }, [acceptedIds, rejectedIds, commentedIds, onRefresh, clearEdit]);

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

          const searchText = finding.original_text || finding.anchor_text;

          const findingContextText = (finding.title + " " + (finding.description || "")).toLowerCase();
          if (finding.paragraph_index !== undefined && finding.paragraph_index !== null) {
            result = await applyParagraphFormatting(finding.paragraph_index, finding.formatting_fix, searchText);
            if (result.success && result.foundInDocument === false && findingContextText.includes("footnote")) {
              result = await applyGlobalFormatting(finding.formatting_fix, findingContextText);
            }
          } else if (searchText) {
            result = await searchAndApplyFormatting(searchText, finding.formatting_fix);
            if (result.success && result.foundInDocument === false && findingContextText.includes("footnote")) {
              result = await applyGlobalFormatting(finding.formatting_fix, findingContextText);
            }
          } else {
            result = await applyGlobalFormatting(finding.formatting_fix, findingContextText);
          }

          if (result.success && result.applied) {
            await qcApi.resolveFinding(finding.id, {
              status: 'accepted',
              resolution_notes: JSON.stringify({
                message: result.message,
                undo_state: result.previous_state
              }),
            });
            setLocalUndoStates(prev => ({ ...prev, [finding.id]: result.previous_state }));
            setAcceptedIds((prev) => new Set(prev).add(finding.id));
            setCommentedIds((prev) => {
              const next = new Set(prev);
              next.delete(finding.id);
              return next;
            });
            formattingAppliedIds.push(finding.id);
            console.log(`✅ Successfully applied formatting for finding ${finding.id}`);
          } else if (result.success && result.foundInDocument === false) {
            await qcApi.resolveFinding(finding.id, {
              status: 'accepted',
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
            console.log(`ℹ️ Auto-resolved formatting finding ${finding.id} (not found in document)`);
          } else {
            failedIds.push(finding.id);
            console.warn(`⚠️ Failed to apply formatting ${finding.id}: ${result.message}`);
          }
          continue;
        }

        // Handle text replacements
        const text = finding.original_text!;
        const replacement = finding.replacement_text!;

        if (!text || replacement === undefined || replacement === null || text === replacement) {
          console.log(`Accepting finding ${finding.id} without text modification`);
          await qcApi.resolveFinding(finding.id, {
            status: 'accepted',
            applied_text: replacement || '',
          });
          setAcceptedIds((prev) => new Set(prev).add(finding.id));
          setCommentedIds((prev) => {
            const next = new Set(prev);
            next.delete(finding.id);
            return next;
          });
          appliedIds.push(finding.id);
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
            Resolved Suggestions ({resolvedFindings.length})
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
  loading,
  isEditing,
  editValue,
  onEditStart,
  onEditChange,
  onEditSave,
  onEditCancel,
  replacementText
}: any) {
  const isRestrictedLocation = (finding.title + " " + (finding.description || "") + " " + (finding.location || "")).toLowerCase().match(/footnote|footer|header/);
  const isFontConsistency = finding.rule_name?.toUpperCase().includes('FONT CONSISTENCY');
  const isFontSizeFix = isFontConsistency && editValue?.toLowerCase().includes('font size');
  const fontMatch = editValue?.match(/(\d+)/);
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
            {finding.status === 'accepted' ? '✓ Accepted' : finding.status === 'rejected' ? '✗ Rejected' : '✓ Commented'}
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
              title={isRestrictedLocation ? "Comments cannot be added in footnotes or headers/footers" : undefined}
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
