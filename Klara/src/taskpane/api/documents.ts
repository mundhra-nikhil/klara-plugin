import { apiClient } from './client';
import type { Document } from '../types';

export const documentsApi = {
  getDocument: async (id: string): Promise<Document> => {
    const { data } = await apiClient.get(`/documents/${id}`);
    return data.data ?? data;
  },

  getContent: async (id: string): Promise<{ html: string; text: string; source: string; filename: string }> => {
    const { data } = await apiClient.get(`/documents/${id}/content`);
    return data.data ?? data;
  },

  runKlara: async (id: string): Promise<{ job_id: string; status: string; message: string }> => {
    const { data } = await apiClient.post(`/documents/${id}/run-klara`);
    return data.data ?? data;
  },

  downloadDocument: async (id: string, version: 'original' | 'processed'): Promise<void> => {
    const res = await fetch(`${apiClient.defaults.baseURL}/documents/${id}/download?version=${version}`, {
      headers: { Authorization: `Bearer ${await import('./client').then(m => m.getAccessToken() || '')}` },
    });
    if (!res.ok) throw new Error(`Download failed (${res.status})`);
    const blob = await res.blob();
    const disposition = res.headers.get('Content-Disposition') || '';
    const match = /filename="?([^"]+)"?/.exec(disposition);
    const filename = match?.[1] || `document-${version}.docx`;
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  },
};
