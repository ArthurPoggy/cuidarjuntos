/** @type {import('jest').Config} */
module.exports = {
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
      setupFiles: ['<rootDir>/jest.setup.js'],
      transformIgnorePatterns: [
        '/node_modules/(?!(.pnpm|react-native|@react-native|@react-native-community|expo|@expo|@expo-google-fonts|react-navigation|@react-navigation|@sentry/react-native|native-base|react-native-safe-area-context|react-native-svg))',
      ],
    },
  ],
};
