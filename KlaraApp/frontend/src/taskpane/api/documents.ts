import { apiClient } from "./client";
import type { Document } from "../types";

export const documentsApi = {
  getDocument: async (id: string): Promise<Document> => {
    const { data } = await apiClient.get(`/documents/${id}`);
    return data.data ?? data;
  },

  getContent: async (
    id: string
  ): Promise<{ html: string; text: string; source: string; filename: string }> => {
    const { data } = await apiClient.get(`/documents/${id}/content`);
    return data.data ?? data;
  },

  runKlara: async (id: string): Promise<{ job_id: string; status: string; message: string }> => {
    const { data } = await apiClient.post(`/documents/${id}/run-klara`);
    return data.data ?? data;
  },

  downloadDocument: async (id: string, version: "original" | "processed"): Promise<void> => {
    const { getAccessToken } = await import("./client");
    const token = getAccessToken();
    const res = await fetch(
      `${apiClient.defaults.baseURL}/documents/${id}/download?version=${version}`,
      {
        headers: { Authorization: `Bearer ${token || ""}` },
      }
    );
    if (!res.ok) throw new Error(`Download failed (${res.status})`);
    const blob = await res.blob();
    const disposition = res.headers.get("Content-Disposition") || "";
    const match = /filename="?([^"]+)"?/.exec(disposition);
    const filename = match?.[1] || `document-${version}.docx`;
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  },

  syncActiveDocument: async (docData: { title: string; url?: string; blob?: Blob }): Promise<string> => {
    // 1. Get a client ID
    const clientsRes = await apiClient.get('/clients');
    const clients = clientsRes.data.data || clientsRes.data || [];
    if (clients.length === 0) {
      throw new Error("No clients found to associate with document.");
    }
    const clientId = clients[0].id;

    // 2. Create document record. Unwrap consistently with the rest of the codebase.
    const createRes = await apiClient.post('/documents', {
      client_id: clientId,
      title: docData.title || "Document.docx",
      document_type: "formatting",
      validation_mode: "review_assist",
    });
    const responseData = createRes.data.data ?? createRes.data;
    const newDocId: string = responseData.id;
    // The backend provides a pre-built upload URL — use it directly (Bug 2).
    const uploadUrl: string = responseData.upload_url;

    // 3. Upload file binary.
    // Prefix blob_path with docId to prevent same-filename collisions across users (Bug 4).
    if (docData.blob) {
      const { getAccessToken } = await import("./client");
      const token = getAccessToken();
      const safeFilename = `${newDocId}-${docData.title || 'Document.docx'}`;
      
      // The backend provides a fully-formed upload URL (SAS URL or local route).
      // We do NOT append ?document_id= here because it breaks Azure SAS signatures
      // and the backend already included it if needed.
      const targetUrl = uploadUrl || `${apiClient.defaults.baseURL}/documents/upload-local?container=local&blob_path=${encodeURIComponent(safeFilename)}&document_id=${newDocId}`;
      
      const headers: Record<string, string> = {
        Authorization: `Bearer ${token || ""}`,
        "Content-Type": "application/octet-stream",
      };

      // Azure Blob Storage requires the x-ms-blob-type header for direct PUT uploads.
      if (targetUrl.includes('.blob.core.windows.net')) {
        headers['x-ms-blob-type'] = 'BlockBlob';
      }

      const res = await fetch(targetUrl, {
        method: 'PUT',
        headers,
        body: docData.blob,
      });
      if (!res.ok) throw new Error(`Upload failed (${res.status})`);
    }

    return newDocId;
  },
};

