import { Platform } from 'react-native';
import * as Notifications from 'expo-notifications';
import { pushTokensApi } from '../api/endpoints';

export type RegisterPushResult =
  | { status: 'registered'; token: string }
  | { status: 'token-only'; token: string; backendError: unknown }
  | { status: 'unsupported' }
  | { status: 'denied' }
  | { status: 'failed'; error: unknown };

const ANDROID_CHANNEL_ID = 'default';

async function ensureAndroidChannel(): Promise<void> {
  // Android 8+ exige um channel; Android 13+ exige que o channel exista
  // antes de obter o push token. Idempotente — pode ser chamado várias vezes.
  if (Platform.OS !== 'android') return;
  await Notifications.setNotificationChannelAsync(ANDROID_CHANNEL_ID, {
    name: 'Notificações',
    importance: Notifications.AndroidImportance.DEFAULT,
  });
}

function resolveProjectId(explicit?: string): string | undefined {
  if (explicit) return explicit;
  // Fallback: var pública do Expo (EXPO_PUBLIC_* é embutida no bundle em build time).
  const fromEnv = process.env.EXPO_PUBLIC_EAS_PROJECT_ID;
  return fromEnv && fromEnv.length > 0 ? fromEnv : undefined;
}

export async function registerForPushNotifications(
  projectId?: string,
): Promise<RegisterPushResult> {
  if (Platform.OS === 'web') {
    return { status: 'unsupported' };
  }

  const { status: existingStatus } = await Notifications.getPermissionsAsync();
  let finalStatus = existingStatus;

  if (existingStatus !== 'granted') {
    const { status } = await Notifications.requestPermissionsAsync();
    finalStatus = status;
  }

  if (finalStatus !== 'granted') {
    return { status: 'denied' };
  }

  try {
    await ensureAndroidChannel();
  } catch (error) {
    return { status: 'failed', error };
  }

  let expoPushToken: string;
  try {
    const resolved = resolveProjectId(projectId);
    const tokenData = await Notifications.getExpoPushTokenAsync(
      resolved ? { projectId: resolved } : undefined,
    );
    expoPushToken = tokenData.data;
  } catch (error) {
    return { status: 'failed', error };
  }

  const platform = Platform.OS === 'ios' ? 'ios' : 'android';

  try {
    await pushTokensApi.register({ token: expoPushToken, platform });
  } catch (backendError) {
    return { status: 'token-only', token: expoPushToken, backendError };
  }

  return { status: 'registered', token: expoPushToken };
}
