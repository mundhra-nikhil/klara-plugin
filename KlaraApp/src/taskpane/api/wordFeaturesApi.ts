import { apiClient } from './client';

export interface EnableTrackChangesRequest {
  enabled: boolean;
}

export interface ApplyAiEditRequest {
  finding_text: string;
  replacement_text: string;
  occurrence_index?: number;
}

export interface BulkApplyAiEditsRequest {
  fixes: any[];
}

export interface RevisionActionRequest {
  revision_ids: string[];
}

export interface AddCommentRequest {
  text: string;
  range?: any;
}

export interface ReplyCommentRequest {
  text: string;
}

export interface SyncPresenceRequest {
  status: string;
}

export interface ManageConflictRequest {
  conflict_data: any;
}

/**
 * Word Features API Client
 */
export const wordFeaturesApi = {
  // --- Track Changes ---
  getTrackChangesStatus: (documentId: string) =>
    apiClient.get(`/documents/${documentId}/word/track-changes/status`),

  enableTrackChanges: (documentId: string, data: EnableTrackChangesRequest) =>
    apiClient.post(`/documents/${documentId}/word/track-changes/enable`, data),

  applyAiEdit: (documentId: string, data: ApplyAiEditRequest) =>
    apiClient.post(`/documents/${documentId}/word/fixes/apply`, data),

  bulkApplyAiEdits: (documentId: string, data: BulkApplyAiEditsRequest) =>
    apiClient.post(`/documents/${documentId}/word/fixes/bulk-apply`, data),

  getTrackedChanges: (documentId: string) =>
    apiClient.get(`/documents/${documentId}/word/track-changes/revisions`),

  acceptRevisions: (documentId: string, data: RevisionActionRequest) =>
    apiClient.post(`/documents/${documentId}/word/track-changes/revisions/accept`, data),

  rejectRevisions: (documentId: string, data: RevisionActionRequest) =>
    apiClient.post(`/documents/${documentId}/word/track-changes/revisions/reject`, data),

  // --- Comments ---
  getComments: (documentId: string) =>
    apiClient.get(`/documents/${documentId}/word/comments`),

  addComment: (documentId: string, data: AddCommentRequest) =>
    apiClient.post(`/documents/${documentId}/word/comments`, data),

  replyToComment: (documentId: string, commentId: string, data: ReplyCommentRequest) =>
    apiClient.post(`/documents/${documentId}/word/comments/${commentId}/reply`, data),

  resolveComment: (documentId: string, commentId: string) =>
    apiClient.post(`/documents/${documentId}/word/comments/${commentId}/resolve`),

  // --- Co-authoring ---
  getActiveEditors: (documentId: string) =>
    apiClient.get(`/documents/${documentId}/word/coauthoring/editors`),

  syncPresence: (documentId: string, data: SyncPresenceRequest) =>
    apiClient.post(`/documents/${documentId}/word/coauthoring/presence`, data),

  manageConflicts: (documentId: string, data: ManageConflictRequest) =>
    apiClient.post(`/documents/${documentId}/word/coauthoring/conflicts`, data),
};
