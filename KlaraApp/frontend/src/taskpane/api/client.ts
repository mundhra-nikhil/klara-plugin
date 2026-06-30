import axios from 'axios';
import type { TokenResponse } from '../types';

const API_BASE = process.env.API_BASE_URL || 'http://localhost:8000/api/v1';

let accessToken: string | null = null;
let refreshToken: string | null = null;

export function getAccessToken(): string | null {
  return accessToken;
}

export function setTokens(access: string, refresh: string) {
  accessToken = access;
  refreshToken = refresh;
  try {
    localStorage.setItem('klara-access', access);
    localStorage.setItem('klara-refresh', refresh);
  } catch {
    // localStorage may be unavailable in some Office contexts
  }
}

export function clearTokens() {
  accessToken = null;
  refreshToken = null;
  try {
    localStorage.removeItem('klara-access');
    localStorage.removeItem('klara-refresh');
  } catch {
    // ignore
  }
}

function loadStoredTokens() {
  try {
    const access = localStorage.getItem('klara-access');
    const refresh = localStorage.getItem('klara-refresh');
    if (access) accessToken = access;
    if (refresh) refreshToken = refresh;
  } catch {
    // ignore
  }
}

loadStoredTokens();

export const apiClient = axios.create({
  baseURL: API_BASE,
  headers: { 'Content-Type': 'application/json' },
  timeout: 30000,
});

apiClient.interceptors.request.use((config) => {
  if (accessToken) {
    config.headers.Authorization = `Bearer ${accessToken}`;
  }
  return config;
});

apiClient.interceptors.response.use(
  (res) => res,
  async (err) => {
    const config = err.config;
    const isAuthRequest = config?.url?.includes('/auth/');
    if (err.response?.status === 401 && !isAuthRequest && config && !config._retry) {
      config._retry = true;
      const currentRefreshToken = refreshToken;
      if (currentRefreshToken) {
        try {
          const response = await axios.post<TokenResponse>(`${API_BASE}/auth/refresh`, {
            refresh_token: currentRefreshToken,
          });
          setTokens(response.data.access_token, response.data.refresh_token);
          if (config.headers) {
            config.headers.Authorization = `Bearer ${response.data.access_token}`;
          }
          return apiClient(config);
        } catch {
          clearTokens();
          return Promise.reject(new Error('Authentication expired'));
        }
      }
      clearTokens();
      return Promise.reject(new Error('Authentication required'));
    }
    return Promise.reject(err);
  }
);
