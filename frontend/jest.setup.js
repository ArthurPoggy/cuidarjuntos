/* eslint-disable @typescript-eslint/no-var-requires */
// Configuracao global de mocks para o ambiente de testes do app mobile
// (frontend/). Mantém aqui apenas mocks de módulos nativos/Expo que não têm
// mock embutido reconhecido automaticamente pelo preset "jest-expo".

// @react-native-async-storage/async-storage: usa o mock oficial do pacote,
// que mantém os dados em memória em vez de acessar o módulo nativo.
jest.mock('@react-native-async-storage/async-storage', () =>
  require('@react-native-async-storage/async-storage/jest/async-storage-mock')
);

// react-native-safe-area-context: usa o mock oficial do pacote, que provê
// <SafeAreaView>/<SafeAreaProvider> e os hooks de insets sem depender de
// código nativo.
jest.mock('react-native-safe-area-context', () =>
  require('react-native-safe-area-context/jest/mock').default
);

// @react-native-community/datetimepicker: módulo nativo sem mock embutido;
// substituímos por um componente simples para permitir renderização em
// telas que usam DateTimePicker (ex.: PeriodFilter).
jest.mock('@react-native-community/datetimepicker', () => {
  const React = require('react');
  const { View } = require('react-native');
  const MockDateTimePicker = (props) => React.createElement(View, props);
  return {
    __esModule: true,
    default: MockDateTimePicker,
  };
});

// expo-secure-store: usado por AuthContext/client para persistir tokens.
jest.mock('expo-secure-store', () => ({
  getItemAsync: jest.fn(() => Promise.resolve(null)),
  setItemAsync: jest.fn(() => Promise.resolve()),
  deleteItemAsync: jest.fn(() => Promise.resolve()),
}));

// expo-speech: usado por useSpeechToText.
jest.mock('expo-speech', () => ({
  speak: jest.fn(),
  stop: jest.fn(),
  isSpeakingAsync: jest.fn(() => Promise.resolve(false)),
}));

// expo-notifications: usado por utils/notifications.
jest.mock('expo-notifications', () => ({
  setNotificationHandler: jest.fn(),
  scheduleNotificationAsync: jest.fn(() => Promise.resolve('mock-id')),
  cancelScheduledNotificationAsync: jest.fn(() => Promise.resolve()),
  getPermissionsAsync: jest.fn(() =>
    Promise.resolve({ status: 'granted' })
  ),
  requestPermissionsAsync: jest.fn(() =>
    Promise.resolve({ status: 'granted' })
  ),
  addNotificationReceivedListener: jest.fn(() => ({ remove: jest.fn() })),
  addNotificationResponseReceivedListener: jest.fn(() => ({
    remove: jest.fn(),
  })),
  getExpoPushTokenAsync: jest.fn(() =>
    Promise.resolve({ data: 'mock-expo-push-token' })
  ),
  AndroidImportance: { MAX: 5 },
  setNotificationChannelAsync: jest.fn(() => Promise.resolve()),
}));
