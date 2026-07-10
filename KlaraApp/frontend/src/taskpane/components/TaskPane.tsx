import React, { useState, useEffect, useCallback } from 'react';
import type { Finding, QCFinding, ChatMessage } from '../types';
import { qcApi } from '../api/qc';
import { authApi } from '../api/auth';
import { setTokens, clearTokens, getAccessToken } from '../api/client';
import { useFindings } from '../hooks/useFindings';
import { SuggestionsTab } from './SuggestionsTab';
import { ChecksTab } from './ChecksTab';
import { WorkflowsTab } from './WorkflowsTab';
import { ChatInput } from './ChatInput';

function LoginOverlay({ onLogin }: { onLogin: (token: string, user: any) => void }) {
  const [mode, setMode] = useState<'sso' | 'email'>('email');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleEmailLogin = async () => {
    if (!email || !password) return;
    setLoading(true);
    setError('');
    try {
      const resp = await authApi.login({ username: email, password });
      setTokens(resp.access_token, resp.refresh_token);
      try {
        const payload = JSON.parse(atob(resp.access_token.split('.')[1]));
        onLogin(resp.access_token, {
          id: payload.sub || '',
          email: payload.email || email,
          name: payload.display_name || payload.name || email,
          role: payload.role || 'document_specialist',
        });
      } catch {
        onLogin(resp.access_token, { id: '', email, name: email, role: 'document_specialist' });
      }
    } catch (e: any) {
      setError(e.message || 'Login failed');
    } finally {
      setLoading(false);
    }
  };

  const handleSSOLogin = async () => {
    setLoading(true);
    setError('');
    try {
      const token = await authApi.getSsoToken();
      if (token) {
        setTokens(token, 'sso-token');
        try {
          const payload = JSON.parse(atob(token.split('.')[1]));
          onLogin(token, {
            id: payload.sub || '',
            email: payload.email || payload.upn || '',
            name: payload.display_name || payload.name || '',
            role: payload.role || 'document_specialist',
          });
        } catch {
          onLogin(token, { id: '', email: '', name: '', role: 'document_specialist' });
        }
      } else {
        setMode('email');
        setError('SSO not available. Please use email/password.');
      }
    } catch (e: any) {
      setMode('email');
      setError(e.message || 'SSO failed. Please use email/password.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="klara-login-overlay">
      <div className="klara-login-box">
        <div className="klara-logo" style={{ width: 36, height: 36, fontSize: 18, margin: '0 auto 12px' }}>K</div>
        <div className="klara-login-title">Sign in to Klara</div>
        <div className="klara-login-subtitle">AI-powered document quality assurance</div>

        {mode === 'email' ? (
          <>
            <input
              className="klara-login-input"
              type="email"
              placeholder="Email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleEmailLogin()}
            />
            <input
              className="klara-login-input"
              type="password"
              placeholder="Password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleEmailLogin()}
            />
            {error && <div style={{ fontSize: 11, color: 'var(--danger)', marginBottom: 8 }}>{error}</div>}
            <button className="klara-login-btn" disabled={loading} onClick={handleEmailLogin}>
              {loading ? 'Signing in...' : 'Sign in'}
            </button>
            <div className="klara-login-divider">or</div>
            <button className="klara-sso-btn" onClick={handleSSOLogin}>
              Sign in with Microsoft
            </button>
          </>
        ) : (
          <>
            <button className="klara-sso-btn" disabled={loading} onClick={handleSSOLogin}>
              {loading ? 'Signing in...' : 'Sign in with Microsoft'}
            </button>
            <div className="klara-login-divider">or</div>
            <button className="klara-login-btn" onClick={() => setMode('email')}>
              Use email/password
            </button>
          </>
        )}
      </div>
    </div>
  );
}

// Derives a short cache key for the currently open document using its URL
// (or title as a fallback) so we can skip re-uploading on every login.
function getDocCacheKey(): string {
  try {
    const docUrl = Office.context.document.url || '';
    return `klara_doc_id:${docUrl || 'untitled'}`;
  } catch {
    return 'klara_doc_id:untitled';
  }
}

export function TaskPane() {
  const [token, setToken] = useState<string | null>(null);
  const [user, setUser] = useState<any>(null);
  const [activeTab, setActiveTab] = useState<'suggestions' | 'checks' | 'workflows'>('suggestions');
  const [docId, setDocId] = useState<string | null>(null);
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isSyncing, setIsSyncing] = useState(false);
  const [syncError, setSyncError] = useState<string | null>(null);

  const { data: findings = [] } = useFindings(docId);

  useEffect(() => {
    const stored = getAccessToken();
    if (stored) {
      setToken(stored);
      try {
        const payload = JSON.parse(atob(stored.split('.')[1]));
        setUser({
          id: payload.sub || '',
          email: payload.email || '',
          name: payload.display_name || payload.name || '',
          role: payload.role || 'document_specialist',
        });
      } catch {
        // ignore parse errors
      }
    }
    setIsLoading(false);
  }, []);

  const handleLogin = useCallback((t: string, u: any) => {
    setToken(t);
    setUser(u);
  }, []);

  const handleLogout = useCallback(() => {
    clearTokens();
    // Clear the document cache so next login re-syncs the file.
    try { sessionStorage.removeItem(getDocCacheKey()); } catch { /* ignore */ }
    setToken(null);
    setUser(null);
    setDocId(null);
    setSyncError(null);
  }, []);

  const loadDocument = useCallback(async () => {
    if (!token) return;

    // Check sessionStorage cache first — avoids re-uploading on every login
    // while the same document is still open in this Word session.
    const cacheKey = getDocCacheKey();
    const cached = sessionStorage.getItem(cacheKey);
    if (cached) {
      console.log('Using cached docId for this session:', cached);
      setDocId(cached);
      return;
    }

    setIsSyncing(true);
    setSyncError(null);
    try {
      console.log('Syncing active document...');
      const { getActiveDocumentData } = await import('../word');
      const docData = await getActiveDocumentData();

      const { documentsApi } = await import('../api/documents');
      const newDocId = await documentsApi.syncActiveDocument(docData);

      sessionStorage.setItem(cacheKey, newDocId);
      setDocId(newDocId);
    } catch (error: any) {
      console.error('Failed to sync active document:', error);
      setSyncError(error?.message || 'Failed to sync document with Klara.');
    } finally {
      setIsSyncing(false);
    }
  }, [token]);

  useEffect(() => {
    if (token) {
      loadDocument();
    }
  }, [token, loadDocument]);

  const openFindingsCount = findings.filter(f => f.status.toLowerCase() === 'open').length;

  if (isLoading) {
    return (
      <div className="klara-loading">
        <div className="klara-loading-spinner" />
        Loading Klara...
      </div>
    );
  }

  if (!token) {
    return <LoginOverlay onLogin={handleLogin} />;
  }

  if (isSyncing) {
    return (
      <div className="klara-loading">
        <div className="klara-loading-spinner" />
        Syncing document...
      </div>
    );
  }

  if (syncError) {
    return (
      <div className="klara-loading" style={{ flexDirection: 'column', gap: 12 }}>
        <div style={{ color: 'var(--danger, #e53e3e)', fontSize: 13, textAlign: 'center', padding: '0 16px' }}>
          ⚠️ {syncError}
        </div>
        <button className="klara-login-btn" onClick={loadDocument}>
          Retry
        </button>
        <button className="klara-sso-btn" onClick={handleLogout} style={{ marginTop: 0 }}>
          Sign out
        </button>
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', position: 'relative' }}>
      <div className="klara-header">
        <div className="klara-logo">K</div>
        <div className="klara-header-info">
          <div className="klara-header-title">Klara for Word</div>
          <div className="klara-header-subtitle">{user?.name || 'User'} · {user?.role?.replace('_', ' ') || 'Specialist'}</div>
        </div>
        <button className="klara-close-btn" title="Sign out" onClick={handleLogout}>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
            <polyline points="16 17 21 12 16 7" />
            <line x1="21" y1="12" x2="9" y2="12" />
          </svg>
        </button>
      </div>

      <div className="klara-tabs">
        <button
          className={`klara-tab ${activeTab === 'suggestions' ? 'active' : ''}`}
          onClick={() => setActiveTab('suggestions')}
        >
          Suggestions
          {openFindingsCount > 0 && <span className="klara-badge">{openFindingsCount}</span>}
        </button>
        <button
          className={`klara-tab ${activeTab === 'checks' ? 'active' : ''}`}
          onClick={() => setActiveTab('checks')}
        >
          Checks
        </button>
        <button
          className={`klara-tab ${activeTab === 'workflows' ? 'active' : ''}`}
          onClick={() => setActiveTab('workflows')}
        >
          Workflows
        </button>
      </div>

      <div className="klara-content">
        {activeTab === 'suggestions' && (
          <SuggestionsTab findings={findings} docId={docId} />
        )}
        {activeTab === 'checks' && <ChecksTab findings={findings} docId={docId} />}
        {activeTab === 'workflows' && (
          <WorkflowsTab 
            docId={docId} 
            onDocSynced={(newId) => {
              setDocId(newId);
              try { sessionStorage.setItem(getDocCacheKey(), newId); } catch {}
            }} 
          />
        )}
      </div>

      <ChatInput messages={chatMessages} onSend={(msg) => setChatMessages((prev) => [...prev.slice(-49), msg])} />
    </div>
  );
}
