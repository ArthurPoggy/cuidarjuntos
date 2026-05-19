import React, { useEffect } from 'react';
import { Platform } from 'react-native';
import { StatusBar } from 'expo-status-bar';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import * as Notifications from 'expo-notifications';
import { AuthProvider } from './src/contexts/AuthContext';
import RootNavigator from './src/navigation/RootNavigator';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 1000 * 60 * 5, // 5 minutes
      retry: 1,
    },
  },
});

// Espelha o `defaultChannel` declarado no app.json (plugin expo-notifications).
// Sem criar o channel em runtime, notificações com esse channel ID não são
// exibidas em Android — a config estática sozinha não basta.
const ANDROID_NOTIFICATION_CHANNEL_ID = 'default';

async function ensureDefaultAndroidChannel(): Promise<void> {
  if (Platform.OS !== 'android') return;
  await Notifications.setNotificationChannelAsync(ANDROID_NOTIFICATION_CHANNEL_ID, {
    name: 'Notificações',
    importance: Notifications.AndroidImportance.DEFAULT,
  });
}

export default function App() {
  useEffect(() => {
    // Falha silenciosa: se o channel não puder ser criado, ainda assim
    // o app deve subir normalmente. Erros aparecem no log do Expo.
    ensureDefaultAndroidChannel().catch(() => {});
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
