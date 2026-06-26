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

  getSsoToken: async (): Promise<string | null> => {
    try {
      // @ts-ignore
      const token = await window.Office.context.auth.getSsoToken({
        ssoUrl: 'https://login.microsoftonline.com',
        ssoTarget: 'MSAccount',
      });
      return token || null;
    } catch {
      return null;
    }
  },
};
