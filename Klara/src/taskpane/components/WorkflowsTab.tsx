import React, { useState, useEffect, useCallback } from 'react';
import { aiJobsApi } from '../api/ai-jobs';
import type { AIJob } from '../types';

const JOB_TYPES = [
  {
    type: 'full_analysis' as const,
    title: 'Run full QC pass',
    desc: 'All 28 checks against profile',
  },
  {
    type: 'format_check' as const,
    title: 'Apply client template',
    desc: 'Formatting rules and style guide',
  },
  {
    type: 'citation_check' as const,
    title: 'Generate TOA',
    desc: 'Citation extraction + format',
  },
  {
    type: 'numbering_check' as const,
    title: 'Build TOC from headings',
    desc: "Match style 'Heading 1-3'",
  },
  {
    type: 'spelling_check' as const,
    title: 'Compare to source PDF',
    desc: 'Word-for-word comparison',
  },
];

export function WorkflowsTab() {
  const [activeJob, setActiveJob] = useState<AIJob | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const pollJob = useCallback(async (jobId: string) => {
    const poll = async () => {
      try {
        const job = await aiJobsApi.getJobStatus(jobId);
        setActiveJob(job);
        if (job.status === 'completed' || job.status === 'failed' || job.status === 'cancelled') {
          return;
        }
        setTimeout(poll, 3000);
      } catch {
        // ignore poll errors
      }
    };
    poll();
  }, []);

  const handleTrigger = useCallback(async (jobType: string) => {
    setLoading(true);
    setError('');
    try {
      const job = await aiJobsApi.triggerJob({
        document_id: 'current',
        job_type: jobType as any,
      });
      setActiveJob(job);
      pollJob(job.id);
    } catch (e: any) {
      setError(e.message || 'Failed to trigger job');
    } finally {
      setLoading(false);
    }
  }, [pollJob]);

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
              style={{ width: `${activeJob.progress_pct || 0}%` }}
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
