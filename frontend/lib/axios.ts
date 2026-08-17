// Axios singleton with interceptor chain.
// Using a singleton (not a new axios instance per request) ensures interceptors
// run exactly once and the JWT refresh queue doesn't create race conditions.
import axios, { AxiosError, AxiosInstance, InternalAxiosRequestConfig } from 'axios';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
const API_KEY = process.env.NEXT_PUBLIC_API_KEY || 'dev_key_123';

// Token storage — using module-level variables because:
// 1. localStorage is unavailable during SSR
// 2. We don't want sensitive tokens in Redux/Context (visible in React DevTools)
// 3. This is effectively a private closure only accessible through these exports
let _accessToken: string | null = null;
let _refreshToken: string | null = null;
let _isRefreshing = false;
let _failedQueue: Array<{ resolve: (token: string) => void; reject: (err: unknown) => void }> = [];

export function setTokens(access: string, refresh: string) {
  _accessToken = access;
  _refreshToken = refresh;
  // Persist refresh token across page reloads
  if (typeof window !== 'undefined') {
    sessionStorage.setItem('rft', refresh);
  }
}

export function clearTokens() {
  _accessToken = null;
  _refreshToken = null;
  if (typeof window !== 'undefined') {
    sessionStorage.removeItem('rft');
  }
}

export function getAccessToken(): string | null {
  return _accessToken;
}

// Hydrate refresh token from sessionStorage on first load
export function hydrateTokens(): void {
  if (typeof window !== 'undefined') {
    const rft = sessionStorage.getItem('rft');
    if (rft) _refreshToken = rft;
  }
}

const processQueue = (error: unknown, token: string | null) => {
  _failedQueue.forEach(p => (error ? p.reject(error) : p.resolve(token!)));
  _failedQueue = [];
};

const api: AxiosInstance = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000, // 30s — LLM calls can be slow
  headers: { 'Content-Type': 'application/json' },
});

// REQUEST interceptor: attach auth headers to every outgoing request
api.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    // Perimeter auth key — required by all API endpoints
    if (API_KEY) config.headers['X-API-Key'] = API_KEY;
    // JWT Bearer token for user-specific operations
    if (_accessToken) config.headers['Authorization'] = `Bearer ${_accessToken}`;
    return config;
  },
  (error) => Promise.reject(error),
);

// RESPONSE interceptor: auto-refresh JWT on 401
api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const originalRequest = error.config as InternalAxiosRequestConfig & { _retry?: boolean };

    // Only attempt refresh once per request (prevent infinite loops)
    if (error.response?.status === 401 && !originalRequest._retry && _refreshToken) {
      if (_isRefreshing) {
        // Queue concurrent requests while refresh is in flight
        return new Promise((resolve, reject) => {
          _failedQueue.push({ resolve, reject });
        }).then(token => {
          originalRequest.headers['Authorization'] = `Bearer ${token}`;
          return api(originalRequest);
        });
      }

      originalRequest._retry = true;
      _isRefreshing = true;

      try {
        const { data } = await axios.post(`${API_BASE_URL}/auth/refresh`, {
          refresh_token: _refreshToken,
        });
        setTokens(data.access_token, data.refresh_token);
        processQueue(null, data.access_token);
        originalRequest.headers['Authorization'] = `Bearer ${data.access_token}`;
        return api(originalRequest);
      } catch (refreshError) {
        processQueue(refreshError, null);
        clearTokens();
        // Redirect to login — session expired
        if (typeof window !== 'undefined') window.location.href = '/login?reason=session_expired';
        return Promise.reject(refreshError);
      } finally {
        _isRefreshing = false;
      }
    }

    return Promise.reject(error);
  },
);

export default api;
