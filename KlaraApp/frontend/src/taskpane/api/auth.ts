import { apiClient } from './client';
import type { LoginRequest, TokenResponse } from '../types';

export const authApi = {
  login: async (req: LoginRequest): Promise<TokenResponse> => {
    const { data } = await apiClient.post<TokenResponse>('/auth/login', req);
    return data;
  },

  refreshToken: async (refreshToken: string): Promise<TokenResponse> => {
    const { data } = await apiClient.post<TokenResponse>('/auth/refresh', {
      refresh_token: refreshToken,
    });
    return data;
  },

  logout: async (refreshToken?: string | null): Promise<void> => {
    await apiClient.post('/auth/logout', { refresh_token: refreshToken });
  },

  getMe: async (): Promise<any> => {
    const { data } = await apiClient.get('/auth/me');
    return data;
  },

  getSsoToken: async (): Promise<string | null> => {
    try {
      // @ts-ignore
      const token = await window.Office.context.auth.getAccessToken({
        tenantId: 'common', // Placeholder, should be configured
        clientId: 'common', // Placeholder, should be configured
      });
      return token || null;
    } catch {
      return null;
    }
  },
};
