import React, { useEffect } from 'react';
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

export default function App() {
  useEffect(() => {
    const foregroundSub = Notifications.addNotificationReceivedListener(
      _notification => {
        // notificação recebida com o app em foreground — handler acima já exibe o alerta
      },
    );

    const responseSub = Notifications.addNotificationResponseReceivedListener(
      response => {
        const data = response.notification.request.content.data as Record<string, unknown>;
        const screen = typeof data?.screen === 'string' ? data.screen : null;

        if (screen && navigationRef.isReady()) {
          const params = { ...data };
          delete params.screen;
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          (navigationRef as any).navigate(screen, params);
        }
      },
    );

    return () => {
      foregroundSub.remove();
      responseSub.remove();
    };
  }, []);

  return (
    <SafeAreaProvider>
      <QueryClientProvider client={queryClient}>
        <AuthProvider>
          <StatusBar style="dark" />
          <RootNavigator />
        </AuthProvider>
      </QueryClientProvider>
    </SafeAreaProvider>
  );
}
