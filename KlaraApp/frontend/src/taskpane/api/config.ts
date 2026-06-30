import { apiClient } from "./client";

export interface PocRule {
  id: number;
  track: number;
  track_label: string;
  name: string;
  detail: string;
  type: string;
  severity: string;
  detection: string;
}

export interface MS365Config {
  client_id?: string;
  authority?: string;
  redirect_uri?: string;
  scopes?: string[];
  [key: string]: any;
}

export const configApi = {
  getPocRules: async (): Promise<PocRule[]> => {
    const { data } = await apiClient.get("/config/poc-rules");
    return data.data ?? data;
  },

  getMS365Config: async (): Promise<MS365Config> => {
    const { data } = await apiClient.get("/config/ms365");
    return data.data ?? data;
  },
};
