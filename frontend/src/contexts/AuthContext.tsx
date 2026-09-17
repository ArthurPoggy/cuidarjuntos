import React, { createContext, useContext, useEffect, useState, useCallback } from 'react';
import { getToken, setToken, deleteToken } from '../utils/tokenStorage';
import { useQueryClient } from '@tanstack/react-query';
import { authApi, groupsApi } from '../api/endpoints';
import { registerForPushNotifications } from '../utils/notifications';
import type { User, Tokens, CareGroup } from '../types/models';

interface AuthState {
  user: User | null;
  tokens: Tokens | null;
  group: CareGroup | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  hasGroup: boolean;
}

interface AuthContextType extends AuthState {
  login: (username: string, password: string) => Promise<void>;
  register: (data: {
    full_name: string; cpf: string; birth_date?: string;
    email: string; username: string; password: string;
  }) => Promise<void>;
  logout: () => Promise<void>;
  refreshGroup: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const queryClient = useQueryClient();
  const [state, setState] = useState<AuthState>({
    user: null,
    tokens: null,
    group: null,
    isAuthenticated: false,
    isLoading: true,
    hasGroup: false,
  });

  const loadTokens = useCallback(async () => {
    try {
      const access = await getToken('access_token');
      const refresh = await getToken('refresh_token');
      if (access && refresh) {
        const { data: user } = await authApi.me();
        const { data: groupData } = await groupsApi.current();
        setState({
          user,
          tokens: { access, refresh },
          group: groupData.group,
          isAuthenticated: true,
          isLoading: false,
          hasGroup: !!groupData.group,
        });
      } else {
        setState(s => ({ ...s, isLoading: false }));
      }
    } catch {
      await deleteToken('access_token');
      await deleteToken('refresh_token');
      setState(s => ({ ...s, isLoading: false }));
    }
  }, []);

  useEffect(() => {
    loadTokens();
  }, [loadTokens]);

  const login = useCallback(async (username: string, password: string) => {
    const { data: tokens } = await authApi.login(username, password);
    await setToken('access_token', tokens.access);
    await setToken('refresh_token', tokens.refresh);

    const { data: user } = await authApi.me();
    const { data: groupData } = await groupsApi.current();

    setState({
      user,
      tokens,
      group: groupData.group,
      isAuthenticated: true,
      isLoading: false,
      hasGroup: !!groupData.group,
    });

    // Fire-and-forget: registro de push roda em background para não atrasar
    // a navegação pós-login. A função não lança — retorna RegisterPushResult.
    // O .catch() cobre o caso defensivo de uma rejeição inesperada.
    void registerForPushNotifications().catch(() => {});
  }, []);

  const register = useCallback(async (data: {
    full_name: string; cpf: string; birth_date?: string;
    email: string; username: string; password: string;
  }) => {
    const { data: result } = await authApi.register(data);
    await setToken('access_token', result.tokens.access);
    await setToken('refresh_token', result.tokens.refresh);

    setState({
      user: result.user,
      tokens: result.tokens,
      group: null,
      isAuthenticated: true,
      isLoading: false,
      hasGroup: false,
    });
  }, []);

  const logout = useCallback(async () => {
    await deleteToken('access_token');
    await deleteToken('refresh_token');
    // Limpa todo o cache do React Query para não vazar dados sensíveis (ex.:
    // histórico de chat) para um próximo login no mesmo dispositivo.
    queryClient.clear();
    setState({
      user: null,
      tokens: null,
      group: null,
      isAuthenticated: false,
      isLoading: false,
      hasGroup: false,
    });
  }, [queryClient]);

  const refreshGroup = useCallback(async () => {
    try {
      const { data: groupData } = await groupsApi.current();
      setState(s => ({
        ...s,
        group: groupData.group,
        hasGroup: !!groupData.group,
      }));
    } catch {
      setState(s => ({ ...s, group: null, hasGroup: false }));
    }
  }, []);

  return (
    <AuthContext.Provider value={{ ...state, login, register, logout, refreshGroup }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}
