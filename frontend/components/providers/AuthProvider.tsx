// Auth context provider.
// Manages: JWT tokens, session_id (from /verify), isVerified flag, and user info.
// The dual-token model exists because the backend requires BOTH:
//   - JWT Bearer token (from /auth/login) for all protected routes
//   - session_id (from /verify) passed in request body for banking operations
'use client';
import { createContext, useContext, useReducer, useEffect, useCallback, ReactNode } from 'react';
import { setTokens, clearTokens, hydrateTokens } from '@/lib/axios';
import type { TokenResponse } from '@/types/api.types';

interface User {
  userId: string;
  firstName?: string;
  role: string;
}

interface AuthState {
  user: User | null;
  sessionId: string | null; // From /verify — needed for banking ops
  isVerified: boolean;       // True only after PIN verification succeeds
  isAuthenticated: boolean;  // True after JWT login
  isLoading: boolean;
}

type AuthAction =
  | { type: 'LOGIN'; payload: { user: User; accessToken: string; refreshToken: string } }
  | { type: 'VERIFY'; payload: { sessionId: string; firstName?: string } }
  | { type: 'LOGOUT' }
  | { type: 'SET_LOADING'; payload: boolean };

const initialState: AuthState = {
  user: null,
  sessionId: null,
  isVerified: false,
  isAuthenticated: false,
  isLoading: true,
};

function authReducer(state: AuthState, action: AuthAction): AuthState {
  switch (action.type) {
    case 'LOGIN':
      return {
        ...state,
        user: action.payload.user,
        isAuthenticated: true,
        isLoading: false,
      };
    case 'VERIFY':
      return {
        ...state,
        sessionId: action.payload.sessionId,
        isVerified: true,
        user: state.user ? {
          ...state.user,
          firstName: action.payload.firstName ?? state.user.firstName,
        } : null,
      };
    case 'LOGOUT':
      return { ...initialState, isLoading: false };
    case 'SET_LOADING':
      return { ...state, isLoading: action.payload };
    default:
      return state;
  }
}

interface AuthContextValue extends AuthState {
  login: (res: TokenResponse) => void;
  verify: (sessionId: string, firstName?: string) => void;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(authReducer, initialState);

  // Hydrate persisted refresh token on mount
  useEffect(() => {
    hydrateTokens();
    // Check localStorage for persisted user info ("Remember Device" feature)
    const saved = typeof window !== 'undefined' ? localStorage.getItem('auth_user') : null;
    if (saved) {
      try {
        const parsed = JSON.parse(saved) as User;
        dispatch({ type: 'LOGIN', payload: { user: parsed, accessToken: '', refreshToken: '' } });
      } catch { /* ignore corrupted storage */ }
    }
    dispatch({ type: 'SET_LOADING', payload: false });
  }, []);

  const login = useCallback((res: TokenResponse) => {
    setTokens(res.access_token, res.refresh_token);
    const user: User = { userId: res.user_id, role: 'customer' };
    dispatch({ type: 'LOGIN', payload: { user, accessToken: res.access_token, refreshToken: res.refresh_token } });
  }, []);

  const verify = useCallback((sessionId: string, firstName?: string) => {
    dispatch({ type: 'VERIFY', payload: { sessionId, firstName } });
  }, []);

  const logout = useCallback(() => {
    clearTokens();
    if (typeof window !== 'undefined') localStorage.removeItem('auth_user');
    dispatch({ type: 'LOGOUT' });
  }, []);

  return (
    <AuthContext.Provider value={{ ...state, login, verify, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}
