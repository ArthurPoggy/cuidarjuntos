import React from 'react';
import { NavigationContainer } from '@react-navigation/native';
import { render, waitFor } from '@testing-library/react-native';
import Header from '../Header';

/**
 * Teste de smoke exigido pela tarefa #107 "Ajeitar menu de hamburguer ->
 * MOBILE", item "Preparar infraestrutura de testes automatizados no
 * frontend".
 *
 * Depende de `jest-expo` (preset), `@testing-library/react-native` e
 * `react-test-renderer` estarem instalados como devDependencies e de
 * `jest.config.js` estar configurado (preset "jest-expo" + mocks de
 * `react-native-safe-area-context` e `@react-navigation/native`). Nenhuma
 * dessas peças existe hoje em frontend/ (ver
 * src/__tests__/testAutomationInfra.test.ts), então este arquivo nem chega a
 * ser coletado/executado por `npm test`.
 */

jest.mock('../../contexts/AuthContext', () => ({
  useAuth: () => ({
    user: { id: 1, username: 'demo' },
    group: null,
    isAuthenticated: true,
    hasGroup: false,
    logout: jest.fn(),
  }),
}));

jest.mock('../../hooks/useChat', () => ({
  useChatAvailable: () => ({ data: false }),
}));

jest.mock('../../hooks/useUnreadNotifications', () => ({
  useUnreadNotifications: () => ({ count: 0, refresh: jest.fn() }),
}));

describe('Header - menu de hambúrguer (mobile)', () => {
  it('renderiza o botão de hambúrguer dentro de um NavigationContainer', async () => {
    const { getByTestId, toJSON } = await render(
      <NavigationContainer>
        <Header />
      </NavigationContainer>
    );

    await waitFor(() => {
      expect(toJSON()).not.toBeNull();
    });

    expect(getByTestId('header-menu-button')).toBeTruthy();
  });
});
