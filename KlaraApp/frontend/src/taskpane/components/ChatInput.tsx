import React, { useState, useRef, useCallback } from 'react';
import type { ChatMessage } from '../types';

interface ChatInputProps {
  messages: ChatMessage[];
  onSend: (msg: ChatMessage) => void;
}

export function ChatInput({ messages, onSend }: ChatInputProps) {
  const [input, setInput] = useState('');
  const [sending, setSending] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const handleSend = useCallback(async () => {
    if (!input.trim() || sending) return;
    setSending(true);
    const userMsg: ChatMessage = {
      id: `user-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
      role: 'user',
      content: input.trim(),
      timestamp: Date.now(),
    };
    onSend(userMsg);
    setInput('');

    // Stubbed response - backend chat endpoint not yet implemented
    await new Promise((r) => setTimeout(r, 800));
    const aiMsg: ChatMessage = {
      id: `ai-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
      role: 'assistant',
      content: 'This is a stubbed response. The backend chat endpoint needs to be implemented at `POST /documents/:id/chat` or `POST /ai-jobs/chat`.',
      timestamp: Date.now(),
    };
    onSend(aiMsg);
    setSending(false);
  }, [input, sending, onSend]);

  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }, [handleSend]);

  return (
    <div className="klara-chat-footer">
      {messages.length > 0 && (
        <div className="klara-chat-messages">
          {messages.slice(-50).map((msg) => (
            <div key={msg.id} className={`klara-chat-msg ${msg.role === 'user' ? 'klara-chat-msg-user' : 'klara-chat-msg-ai'}`}>
              {msg.content}
            </div>
          ))}
        </div>
      )}
      <div className="klara-chat-box">
        <div className="klara-chat-placeholder">Ask Klara about this document…</div>
        <div className="klara-chat-row">
          <button className="klara-chat-icon-btn" title="Upload file">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
              <polyline points="17 8 12 3 7 8" />
              <line x1="12" y1="3" x2="12" y2="15" />
            </svg>
          </button>
          <button className="klara-chat-icon-btn" title="AI assist">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z" />
            </svg>
          </button>
          <input
            ref={inputRef}
            className="klara-chat-input"
            type="text"
            placeholder="Ask Klara about this document…"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={sending}
          />
          <span className="klara-chat-mode">
            Auto
            <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <polyline points="6 9 12 15 18 9" />
            </svg>
          </span>
          <button
            className="klara-btn klara-btn-primary klara-btn-sm"
            onClick={handleSend}
            disabled={sending || !input.trim()}
            style={{ padding: '3px 8px' }}
          >
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <line x1="22" y1="2" x2="11" y2="13" />
              <polygon points="22 2 15 22 11 13 2 9 22 2" />
            </svg>
          </button>
        </div>
      </div>
    </div>
  );
}
