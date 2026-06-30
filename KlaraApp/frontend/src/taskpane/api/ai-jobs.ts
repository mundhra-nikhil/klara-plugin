import { apiClient } from "./client";
import type { AIJob, Finding, TriggerAIJobRequest } from "../types";

export const aiJobsApi = {
  triggerJob: async (req: TriggerAIJobRequest): Promise<AIJob> => {
    const { data } = await apiClient.post("/ai-jobs", req);
    return data.data ?? data;
  },

  getJobStatus: async (id: string): Promise<AIJob> => {
    const { data } = await apiClient.get(`/ai-jobs/${id}`);
    return data.data ?? data;
  },

  cancelJob: async (id: string): Promise<void> => {
    await apiClient.delete(`/ai-jobs/${id}/cancel`);
  },

  getFindings: async (jobId: string): Promise<Finding[]> => {
    const { data } = await apiClient.get(`/ai-jobs/${jobId}/findings`);
    return data.data ?? data;
  },
};
