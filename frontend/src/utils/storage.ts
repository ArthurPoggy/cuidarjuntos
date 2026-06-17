import { Platform } from 'react-native';
import * as SecureStore from 'expo-secure-store';

/**
 * Storage de tokens com suporte a web.
 *
 * No app nativo (iOS/Android) usa expo-secure-store (Keychain/Keystore).
 * Na web, expo-secure-store NÃO é suportado, então caímos para localStorage.
 *
 * Mesma assinatura nas duas plataformas: getItem / setItem / removeItem.
 */
const isWeb = Platform.OS === 'web';

export const tokenStorage = {
  async getItem(key: string): Promise<string | null> {
    if (isWeb) {
      try {
        return window.localStorage.getItem(key);
      } catch {
        return null;
      }
    }
    return SecureStore.getItemAsync(key);
  },

  async setItem(key: string, value: string): Promise<void> {
    if (isWeb) {
      try {
        window.localStorage.setItem(key, value);
      } catch {
        /* ignore */
      }
      return;
    }
    await SecureStore.setItemAsync(key, value);
  },

  async removeItem(key: string): Promise<void> {
    if (isWeb) {
      try {
        window.localStorage.removeItem(key);
      } catch {
        /* ignore */
      }
      return;
    }
    await SecureStore.deleteItemAsync(key);
  },
};
