import React, { useState, useEffect, useCallback } from 'react';
import { qcApi } from '../api/qc';
import { searchAndSelect, highlightRange, clearHighlights } from '../word-context';
import type { ChecklistItem } from '../types';

const RESULT_COLORS: Record<string, string> = {
  pass: 'var(--success)',
  fail: 'var(--danger)',
  warn: 'var(--warn)',
  pending: 'var(--muted-3)',
};

interface GroupedItems {
  group: string;
  items: ChecklistItem[];
}

export function ChecksTab() {
  const [items, setItems] = useState<GroupedItems[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [summary, setSummary] = useState({ pass: 0, fail: 0, warn: 0, pending: 0 });

  const loadChecks = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const checklists = await qcApi.getChecklists('document_review');
      if (checklists.length > 0) {
        const allItems = checklists[0].items;
        const grouped: Record<string, ChecklistItem[]> = {};
        for (const item of allItems) {
          if (!grouped[item.group]) grouped[item.group] = [];
          grouped[item.group].push(item);
        }
        const groupedItems: GroupedItems[] = Object.entries(grouped).map(([group, items]) => ({ group, items }));
        setItems(groupedItems);

        const pass = allItems.filter((i) => i.result === 'pass').length;
        const fail = allItems.filter((i) => i.result === 'fail').length;
        const warn = allItems.filter((i) => i.result === 'warn').length;
        const pending = allItems.filter((i) => i.result === 'pending').length;
        setSummary({ pass, fail, warn, pending });
      } else {
        setItems([]);
      }
    } catch (e: any) {
      setError(e.message || 'Failed to load checks');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadChecks();
  }, [loadChecks]);

  const handleNavigate = useCallback(async (item: ChecklistItem) => {
    if (item.result === 'pending') return;
    await clearHighlights();
    const text = item.title;
    const range = await searchAndSelect(text, 0);
    if (range) {
      const color = RESULT_COLORS[item.result] || 'yellow';
      await highlightRange(range, color);
    }
  }, []);

  if (loading) {
    return (
      <div className="klara-loading">
        <div className="klara-loading-spinner" />
        Loading checks...
      </div>
    );
  }

  if (error) {
    return (
      <div style={{ padding: 14, fontSize: 11, color: 'var(--danger)' }}>
        {error}
      </div>
    );
  }

  if (items.length === 0) {
    return (
      <div className="klara-empty">
        <div className="klara-empty-icon">☑</div>
        <div className="klara-empty-text">No checks configured</div>
      </div>
    );
  }

  return (
    <div>
      <div className="klara-summary">
        <div className="klara-summary-item">
          <div className="klara-summary-dot" style={{ background: 'var(--success)' }} />
          {summary.pass} pass
        </div>
        <div className="klara-summary-item">
          <div className="klara-summary-dot" style={{ background: 'var(--danger)' }} />
          {summary.fail} fail
        </div>
        <div className="klara-summary-item">
          <div className="klara-summary-dot" style={{ background: 'var(--warn)' }} />
          {summary.warn} warn
        </div>
        <div className="klara-summary-item">
          <div className="klara-summary-dot" style={{ background: 'var(--muted-3)' }} />
          {summary.pending} pending
        </div>
      </div>

      {items.map(({ group, items: groupItems }) => (
        <div key={group}>
          <div className="klara-group-header">{group}</div>
          {groupItems.map((item) => (
            <div
              key={item.id}
              className="klara-checklist-item"
              onClick={() => handleNavigate(item)}
              style={{ opacity: item.result === 'pending' ? 0.6 : 1 }}
            >
              <div className={`klara-dot klara-dot-${item.result}`} />
              <div className="klara-checklist-title">{item.title}</div>
            </div>
          ))}
        </div>
      ))}
    </div>
  );
}
