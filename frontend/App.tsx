import React, { useCallback, useEffect, useRef } from 'react';
import { Platform } from 'react-native';
import { StatusBar } from 'expo-status-bar';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import * as Notifications from 'expo-notifications';
import { AuthProvider } from './src/contexts/AuthContext';
import RootNavigator from './src/navigation/RootNavigator';
import { navigationRef } from './src/navigation/navigationRef';

Notifications.setNotificationHandler({
  handleNotification: async () => ({
    shouldShowAlert: true,
    shouldShowBanner: true,
    shouldShowList: true,
    shouldPlaySound: true,
    shouldSetBadge: false,
  }),
});

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 1000 * 60 * 5,
      retry: 1,
    },
  },
});

type NavTarget = { screen: string; params: Record<string, unknown> };

function extractTarget(response: Notifications.NotificationResponse): NavTarget | null {
  const data = response.notification.request.content.data as Record<string, unknown> | undefined;
  const screen = data && typeof data.screen === 'string' ? data.screen : null;
  if (!screen) return null;
  const params: Record<string, unknown> = { ...(data ?? {}) };
  delete params.screen;
  return { screen, params };
}

function navigateToTarget(target: NavTarget) {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  (navigationRef as any).navigate(target.screen, target.params);
}

export default function App() {
  // Guarda o destino vindo de uma notificação enquanto o navigator
  // ainda não está pronto (caso típico: cold start).
  const pendingTargetRef = useRef<NavTarget | null>(null);

  const handleResponse = useCallback((response: Notifications.NotificationResponse) => {
    const target = extractTarget(response);
    if (!target) return;
    if (navigationRef.isReady()) {
      navigateToTarget(target);
    } else {
      pendingTargetRef.current = target;
    }
  }, []);

  const handleNavReady = useCallback(() => {
    const target = pendingTargetRef.current;
    if (target && navigationRef.isReady()) {
      pendingTargetRef.current = null;
      navigateToTarget(target);
    }
  }, []);

  useEffect(() => {
    // expo-notifications não é suportado na web — evita rejeições/erros lá.
    if (Platform.OS === 'web') return;

    // Cold start: o app pode ter sido aberto justamente por toque numa
    // notificação. O listener não cobre esse caso de forma confiável —
    // a última response precisa ser consultada explicitamente.
    let cancelled = false;
    Notifications.getLastNotificationResponseAsync().then(response => {
      if (!cancelled && response) handleResponse(response);
    });

    const foregroundSub = Notifications.addNotificationReceivedListener(() => {
      // Notificação recebida com o app em foreground — handler global já exibe.
    });

    const responseSub = Notifications.addNotificationResponseReceivedListener(handleResponse);

    return () => {
      cancelled = true;
      foregroundSub.remove();
      responseSub.remove();
    };
  }, [handleResponse]);

  return (
    <SafeAreaProvider>
      <QueryClientProvider client={queryClient}>
        <AuthProvider>
          <StatusBar style="dark" />
          <RootNavigator onReady={handleNavReady} />
        </AuthProvider>
      </QueryClientProvider>
    </SafeAreaProvider>
  );
}
