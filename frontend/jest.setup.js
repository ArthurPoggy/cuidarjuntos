// Mocks globais usados por todos os testes do app mobile.
//
// react-native-safe-area-context: substitui a implementação nativa (que
// depende de medições reais de tela) pelo mock oficial da biblioteca, que
// fornece um SafeAreaProvider simplificado e insets padrão (0) sem exigir
// que cada teste envolva a árvore num <SafeAreaProvider> real.
jest.mock('react-native-safe-area-context', () => {
  const mock = require('react-native-safe-area-context/jest/mock');
  return mock.default ?? mock;
});
