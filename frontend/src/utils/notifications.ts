import { Platform } from 'react-native';
import * as Notifications from 'expo-notifications';
import { pushTokensApi } from '../api/endpoints';

export async function registerForPushNotifications(): Promise<string | null> {
  if (Platform.OS === 'web') {
    return null;
  }

  const { status: existingStatus } = await Notifications.getPermissionsAsync();
  let finalStatus = existingStatus;

  if (existingStatus !== 'granted') {
    const { status } = await Notifications.requestPermissionsAsync();
    finalStatus = status;
  }

  if (finalStatus !== 'granted') {
    return null;
  }

  let expoPushToken: string;
  try {
    const tokenData = await Notifications.getExpoPushTokenAsync();
    expoPushToken = tokenData.data;
  } catch {
    return null;
  }

  const platform = Platform.OS === 'ios' ? 'ios' : 'android';

  try {
    await pushTokensApi.register({ token: expoPushToken, platform });
  } catch {
    // Token obtained but registration failed — return it anyway so caller knows
  }

  return expoPushToken;
}
