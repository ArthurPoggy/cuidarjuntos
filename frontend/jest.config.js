/**
 * Minimal Jest config for the frontend package.
 *
 * We deliberately avoid the `jest-expo` preset here: it depends on
 * `babel-preset-expo`, which is not part of this package's declared
 * dependencies, and it would also pull in the full React Native test
 * environment which is unnecessary for testing plain TypeScript utility
 * modules (e.g. src/utils/date.ts). A lightweight Babel transform (TS ->
 * CommonJS) is enough and keeps the test setup fast and dependency-light.
 */
module.exports = {
  testEnvironment: 'node',
  testMatch: ['<rootDir>/src/**/__tests__/**/*.test.ts', '<rootDir>/src/**/*.test.ts'],
  transform: {
    '^.+\\.tsx?$': [
      'babel-jest',
      {
        presets: ['@babel/preset-typescript'],
        plugins: ['@babel/plugin-transform-modules-commonjs'],
      },
    ],
  },
  moduleFileExtensions: ['ts', 'tsx', 'js', 'json'],
  testPathIgnorePatterns: ['/node_modules/', '/dist/'],
};
