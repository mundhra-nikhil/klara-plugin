import { apiClient } from './client';
import type { PocRule } from '../types';

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

export const configApi = {
  getPocRules: async (): Promise<PocRule[]> => {
    const { data } = await apiClient.get('/config/poc-rules');
    return data.data ?? data;
  },

  getMS365Config: async (): Promise<any> => {
    const { data } = await apiClient.get('/config/ms365');
    return data.data ?? data;
  },
};
