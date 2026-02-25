import React, { createContext, useContext, useEffect, useState, useCallback } from 'react';
import * as SecureStore from 'expo-secure-store';
import { authApi, groupsApi } from '../api/endpoints';
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
      const access = await SecureStore.getItemAsync('access_token');
      const refresh = await SecureStore.getItemAsync('refresh_token');
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
      await SecureStore.deleteItemAsync('access_token');
      await SecureStore.deleteItemAsync('refresh_token');
      setState(s => ({ ...s, isLoading: false }));
    }
  }, []);

  useEffect(() => {
    loadTokens();
  }, [loadTokens]);

  const login = useCallback(async (username: string, password: string) => {
    const { data: tokens } = await authApi.login(username, password);
    await SecureStore.setItemAsync('access_token', tokens.access);
    await SecureStore.setItemAsync('refresh_token', tokens.refresh);

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
  }, []);

  const register = useCallback(async (data: {
    full_name: string; cpf: string; birth_date?: string;
    email: string; username: string; password: string;
  }) => {
    const { data: result } = await authApi.register(data);
    await SecureStore.setItemAsync('access_token', result.tokens.access);
    await SecureStore.setItemAsync('refresh_token', result.tokens.refresh);

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
    await SecureStore.deleteItemAsync('access_token');
    await SecureStore.deleteItemAsync('refresh_token');
    setState({
      user: null,
      tokens: null,
      group: null,
      isAuthenticated: false,
      isLoading: false,
      hasGroup: false,
    });
  }, []);

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
