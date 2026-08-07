/** @type {import('jest').Config} */
module.exports = {
  testTimeout: 20000,
  projects: [
    {
      displayName: 'ts-jest',
      preset: 'ts-jest',
      testEnvironment: 'node',
      testMatch: ['<rootDir>/src/**/__tests__/**/*.test.ts'],
      clearMocks: true,
    },
    {
      displayName: 'jest-expo',
      preset: 'jest-expo',
      testMatch: ['<rootDir>/src/**/__tests__/**/*.test.tsx'],
      setupFilesAfterEnv: ['<rootDir>/jest.setup.js'],
      transformIgnorePatterns: [
        'node_modules/(?!((jest-)?react-native|@react-native(-community)?)|expo(nent)?|@expo(nent)?/.*|@expo-google-fonts/.*|react-navigation|@react-navigation/.*|@unimodules/.*|unimodules|sentry-expo|native-base|react-native-svg|react-native-safe-area-context|react-native-screens|react-native-calendars|react-native-chart-kit)',
      ],
    },
  ],
};
