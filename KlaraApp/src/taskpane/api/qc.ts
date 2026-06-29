import { apiClient } from './client';
import type { QCFinding, QCReview, Checklist, ResolveFindingRequest } from '../types';

export const qcApi = {
  getFindings: async (documentId: string): Promise<QCFinding[]> => {
    const { data } = await apiClient.get('/qc/findings', { params: { document_id: documentId } });
    const items = data.data ?? data;
    return items.map((item: any) => {
      const loc = (typeof item.location === 'object' && item.location) ? item.location : {};
      return {
        ...item,
        title: loc.title || item.title || '',
        rule_name: loc.rule_name || item.rule_name || '',
        original_text: loc.original_text || item.original_text || '',
        anchor_text: loc.anchor_text || '',
        replacement_text: loc.replacement_text || item.replacement_text || '',
        paragraph_index: loc.paragraph,
      };
    });
  },

  resolveFinding: async (id: string, req: ResolveFindingRequest): Promise<QCFinding> => {
    const { data } = await apiClient.patch(`/qc/findings/${id}/resolve`, req);
    return data.data ?? data;
  },

  getReviews: async (documentId?: string): Promise<QCReview[]> => {
    const { data } = await apiClient.get('/qc/reviews', { params: documentId ? { document_id: documentId } : undefined });
    const body = data.data ?? data;
    const result = Array.isArray(body) ? body : (body.data || body.items);
    if (!Array.isArray(result)) {
      throw new Error(`Unexpected API response structure: expected an array of reviews, got ${typeof body}`);
    }
    return result;
  },

  getChecklists: async (docType: string, clientId?: string): Promise<Checklist[]> => {
    const { data } = await apiClient.get('/qc/checklists', {
      params: { type: docType, client_id: clientId },
    });
    return data.data ?? data;
  },

  getChecklistStatuses: async (reviewId: string): Promise<any[]> => {
    const { data } = await apiClient.get(`/qc/reviews/${reviewId}/checklist-items`);
    return data.data ?? data;
  },

  startReview: async (documentId: string): Promise<QCReview> => {
    const { data } = await apiClient.post('/qc/reviews', { document_id: documentId });
    return data.data ?? data;
  },
};
