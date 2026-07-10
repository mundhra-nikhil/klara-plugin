import React, { useState, useCallback, useRef, useEffect } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { aiJobsApi } from '../api/ai-jobs';
import type { AIJob } from '../types';

const JOB_TYPES = [
  {
    type: 'compliance_audit' as const,
    title: 'Run full QC pass',
    desc: 'All 28 checks against profile',
  },
  {
    type: 'formatting_check' as const,
    title: 'Apply client template',
    desc: 'Formatting rules and style guide',
  },
  {
    type: 'style_validation' as const,
    title: 'Generate TOA',
    desc: 'Citation extraction + format',
  },
  {
    type: 'proofreading' as const,
    title: 'Build TOC from headings',
    desc: "Match style 'Heading 1-3'",
  },
  {
    type: 'pdf_comparison' as const,
    title: 'Compare to source PDF',
    desc: 'Word-for-word comparison',
  },
];

export function WorkflowsTab({ docId, onDocSynced }: { docId: string | null; onDocSynced?: (newId: string) => void }) {
  const queryClient = useQueryClient();
  const [activeJob, setActiveJob] = useState<AIJob | null>(null);
  const [simulatedProgress, setSimulatedProgress] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  
  const pollTimerRef = useRef<NodeJS.Timeout | number>();
  const isMounted = useRef(true);

  useEffect(() => {
    isMounted.current = true;
    return () => {
      isMounted.current = false;
      if (pollTimerRef.current) clearTimeout(pollTimerRef.current as number);
    };
  }, []);

  useEffect(() => {
    if (activeJob) {
      if (activeJob.status === 'running' || activeJob.status === 'analysing' || activeJob.status === 'queued') {
        const timer = setInterval(() => {
          setSimulatedProgress(p => {
            if (p < 90) return p + Math.floor(Math.random() * 10) + 1;
            return p;
          });
        }, 1500);
        return () => clearInterval(timer);
      } else if (activeJob.status === 'completed') {
        setSimulatedProgress(100);
      }
    } else {
      setSimulatedProgress(0);
    }
    return undefined;
  }, [activeJob?.status]);

  const pollJob = useCallback(async (jobId: string, currentDocId: string) => {
    console.log(`Starting to poll job ${jobId}`);
    let failures = 0;
    const poll = async () => {
      if (!isMounted.current) return;
      try {
        const job = await aiJobsApi.getJobStatus(jobId);
        if (!isMounted.current) return;
        failures = 0;
        console.log(`Job ${jobId} status: ${job.status}, progress: ${job.progress_pct || 0}%`);
        setActiveJob(job);
        if (job.status === 'completed' || job.status === 'failed' || job.status === 'cancelled') {
          console.log(`Job ${jobId} finished with status: ${job.status}`);
          if (job.status === 'completed') {
            queryClient.invalidateQueries({ queryKey: ['findings', currentDocId] });
          }
          return;
        }
        pollTimerRef.current = setTimeout(poll, 3000) as any;
      } catch (err) {
        console.error(`Failed to poll job ${jobId}:`, err);
        failures++;
        if (failures >= 5) {
          if (isMounted.current) setError('Failed to get job status after multiple retries.');
          return;
        }
        if (isMounted.current) {
          pollTimerRef.current = setTimeout(poll, 3000) as any;
        }
      }
    };
    poll();
  }, []);

  const handleTrigger = useCallback(async (jobType: string) => {
    setLoading(true);
    setError('');

    try {
      let currentDocId = docId;
      if (!currentDocId) {
        throw new Error('No document selected. Please make sure a document is available.');
      }

      try {
        const { getActiveDocumentData } = await import('../word-context');
        const docData = await getActiveDocumentData();
        const { documentsApi } = await import('../api/documents');
        currentDocId = await documentsApi.syncActiveDocument(docData);
        if (onDocSynced) onDocSynced(currentDocId);
      } catch (err: any) {
        console.warn('Failed to re-sync document before job.', err);
        throw new Error('Failed to extract document. Please ensure your document is saved and try again.');
      }

      console.log(`Triggering AI job: ${jobType} for document: ${currentDocId}`);
      const job = await aiJobsApi.triggerJob({
        document_id: currentDocId,
        job_type: (jobType as any) || 'formatting_check',
      });
      console.log(`AI job created successfully: ${job.id}`);
      setSimulatedProgress(0);
      setActiveJob(job);
      pollJob(job.id, currentDocId);
    } catch (e: any) {
      console.error('Failed to trigger AI job:', e);
      setError(e.message || 'Failed to trigger job');
    } finally {
      setLoading(false);
    }
  }, [pollJob, docId, queryClient]);

  const handleCancel = useCallback(async () => {
    if (!activeJob) return;
    try {
      await aiJobsApi.cancelJob(activeJob.id);
      setActiveJob(null);
    } catch {
      // ignore
    }
  }, [activeJob]);

  const statusConfig: Record<string, { label: string; color: string }> = {
    queued: { label: 'Queued', color: 'var(--muted)' },
    running: { label: 'Running', color: 'var(--accent)' },
    analysing: { label: 'Analysing', color: 'var(--accent)' },
    completed: { label: 'Completed', color: 'var(--success)' },
    failed: { label: 'Failed', color: 'var(--danger)' },
    cancelled: { label: 'Cancelled', color: 'var(--muted)' },
  };

  return (
    <div>
      {!docId && !error && (
        <div style={{ padding: '14px', fontSize: 11, color: 'var(--muted-2)', textAlign: 'center' }}>
          No document available. Please create or select a document first.
        </div>
      )}

      {activeJob && (
        <div style={{ padding: '12px 14px', borderBottom: '1px solid var(--border)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
            <div style={{ fontSize: 11, fontWeight: 600, flex: 1 }}>
              {JOB_TYPES.find((t) => t.type === activeJob.job_type)?.title || activeJob.job_type}
            </div>
            <div style={{ fontSize: 10, color: statusConfig[activeJob.status]?.color || 'var(--muted)', fontWeight: 600 }}>
              {statusConfig[activeJob.status]?.label || activeJob.status}
            </div>
            {(activeJob.status === 'running' || activeJob.status === 'analysing' || activeJob.status === 'queued') && (
              <button className="klara-btn klara-btn-ghost klara-btn-sm" onClick={handleCancel}>
                Cancel
              </button>
            )}
          </div>
          <div className="klara-progress">
            <div
              className="klara-progress-bar"
              style={{ width: `${activeJob.progress_pct || simulatedProgress}%`, transition: 'width 0.5s ease' }}
            />
          </div>
          {activeJob.error_message && (
            <div style={{ fontSize: 10, color: 'var(--danger)', marginTop: 4 }}>
              {activeJob.error_message}
            </div>
          )}
        </div>
      )}

      {JOB_TYPES.map(({ type, title, desc }) => (
        <button
          key={type}
          className="klara-workflow-btn"
          disabled={loading || (activeJob && activeJob.status === 'running') || (activeJob && activeJob.status === 'analysing')}
          onClick={() => handleTrigger(type)}
        >
          <div className="klara-workflow-title">{title}</div>
          <div className="klara-workflow-desc">{desc}</div>
        </button>
      ))}

      {error && (
        <div style={{ padding: '8px 14px', fontSize: 11, color: 'var(--danger)' }}>
          {error}
        </div>
      )}
    </div>
  );
}
