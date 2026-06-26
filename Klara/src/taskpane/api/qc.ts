import { apiClient } from './client';
import type { QCFinding, QCReview, Checklist, ChecklistItem, ResolveFindingRequest } from '../types';

export const qcApi = {
  getFindings: async (documentId: string): Promise<QCFinding[]> => {
    const { data } = await apiClient.get('/qc/findings', { params: { document_id: documentId } });
    return data.data ?? data;
  },

  resolveFinding: async (id: string, req: ResolveFindingRequest): Promise<QCFinding> => {
    const { data } = await apiClient.patch(`/qc/findings/${id}/resolve`, req);
    return data.data ?? data;
  },

  getReviews: async (documentId?: string): Promise<QCReview[]> => {
    const { data } = await apiClient.get('/qc/reviews', { params: documentId ? { document_id: documentId } : undefined });
    const body = data.data ?? data;
    return Array.isArray(body) ? body : (body.data || body.items || []);
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
