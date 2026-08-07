import React from 'react';
import { NavigationContainer } from '@react-navigation/native';
import { render, fireEvent, waitFor, act } from '@testing-library/react-native';
import Header from '../Header';
import { spacing } from '../../theme';

/**
 * Testes automatizados exigidos pela tarefa #107 "Ajeitar menu de
 * hamburguer -> MOBILE", item "Corrigir abertura/fechamento do menu e
 * sobreposição com header/conteúdo (safe area)".
 *
 * Critérios de aceitação cobertos:
 *  (a) fireEvent.press no botão do hambúrguer -> Modal fica visible=true.
 *  (b) fireEvent.press em modalDismiss (e também onRequestClose, disparado
 *      pelo botão físico de voltar do Android) -> Modal volta a
 *      visible=false.
 *  (c) com useSafeAreaInsets mockado retornando bottom: 34 (iPhone com
 *      notch/home indicator), o paddingBottom do modalContent deve ser
 *      >= 34, para não sobrepor a barra de gestos/home indicator do iOS.
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

// Sobrescreve, apenas para este arquivo de teste, o mock global de
// react-native-safe-area-context (definido em jest.setup.js) para permitir
// controlar o retorno de `useSafeAreaInsets` por teste (necessário para o
// critério (c), que exige simular um iPhone com notch/home indicator).
const mockUseSafeAreaInsets = jest.fn(() => ({ top: 0, bottom: 0, left: 0, right: 0 }));
jest.mock('react-native-safe-area-context', () => {
  const actual = jest.requireActual('react-native-safe-area-context/jest/mock');
  const base = actual.default ?? actual;
  return {
    ...base,
    useSafeAreaInsets: () => mockUseSafeAreaInsets(),
  };
});

/** Percorre a árvore renderizada (toJSON()) procurando o nó `Modal`. */
function findModalNode(node: any): any {
  if (!node) return null;
  if (Array.isArray(node)) {
    for (const child of node) {
      const found = findModalNode(child);
      if (found) return found;
    }
    return null;
  }
  if (node.type === 'Modal') return node;
  if (node.children) return findModalNode(node.children);
  return null;
}

/** Achata um `style` (que pode ser array de objetos) num único objeto. */
function flattenStyle(style: any): Record<string, unknown> {
  if (!style) return {};
  if (Array.isArray(style)) {
    return style.reduce((acc, s) => ({ ...acc, ...flattenStyle(s) }), {});
  }
  return style;
}

/** Acha, dentro da subárvore do Modal, o primeiro nó cujo style tenha `key`. */
function findNodeWithStyleKey(node: any, key: string): any {
  if (!node) return null;
  if (Array.isArray(node)) {
    for (const child of node) {
      const found = findNodeWithStyleKey(child, key);
      if (found) return found;
    }
    return null;
  }
  const flat = flattenStyle(node.props && node.props.style);
  if (Object.prototype.hasOwnProperty.call(flat, key)) return node;
  if (node.children) return findNodeWithStyleKey(node.children, key);
  return null;
}

describe('Header - menu de hambúrguer (mobile)', () => {
  beforeEach(() => {
    mockUseSafeAreaInsets.mockReturnValue({ top: 0, bottom: 0, left: 0, right: 0 });
  });

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

  it('(a) abre o menu (Modal visible=true) ao pressionar o botão de hambúrguer', async () => {
    const { getByTestId, toJSON } = await render(
      <NavigationContainer>
        <Header />
      </NavigationContainer>
    );

    // O mock oficial de `Modal` (react-native/jest/mocks/Modal.js) nem
    // sequer renderiza a subárvore quando `visible` é false, então antes do
    // toque o nó "Modal" não deve existir na árvore renderizada.
    expect(findModalNode(toJSON())).toBeNull();

    await fireEvent.press(getByTestId('header-menu-button'));

    const modalAfter = findModalNode(toJSON());
    expect(modalAfter).toBeTruthy();
    expect(modalAfter.props.visible).toBe(true);
  });

  it('(b) fecha o menu (Modal visible=false) ao tocar na área de dismiss (modalDismiss)', async () => {
    const { getByTestId, toJSON } = await render(
      <NavigationContainer>
        <Header />
      </NavigationContainer>
    );

    await fireEvent.press(getByTestId('header-menu-button'));
    expect(findModalNode(toJSON()).props.visible).toBe(true);

    await fireEvent.press(getByTestId('header-menu-dismiss'));

    // O mock oficial de `Modal` não renderiza a subárvore quando
    // `visible` é false (ver comentário no teste (a)), então "fechado"
    // aqui se traduz em o nó "Modal" deixar de existir na árvore.
    expect(findModalNode(toJSON())).toBeNull();
  });

  it('(b) fecha o menu (Modal visible=false) ao disparar onRequestClose (botão voltar do Android)', async () => {
    const { getByTestId, toJSON } = await render(
      <NavigationContainer>
        <Header />
      </NavigationContainer>
    );

    await fireEvent.press(getByTestId('header-menu-button'));
    expect(findModalNode(toJSON()).props.visible).toBe(true);

    const modalNode = findModalNode(toJSON());
    expect(typeof modalNode.props.onRequestClose).toBe('function');

    // `onRequestClose` é chamado nativamente ao pressionar o botão físico
    // de voltar do Android; simulamos disparando a prop diretamente, já que
    // o Modal mockado não expõe essa interação via `fireEvent`.
    await act(() => {
      modalNode.props.onRequestClose();
    });

    // O mock oficial de `Modal` não renderiza a subárvore quando
    // `visible` é false (ver comentário no teste (a)), então "fechado"
    // aqui se traduz em o nó "Modal" deixar de existir na árvore.
    expect(findModalNode(toJSON())).toBeNull();
  });

  it('(c) aplica paddingBottom >= insets.bottom no modalContent (safe area do iOS, ex: 34)', async () => {
    mockUseSafeAreaInsets.mockReturnValue({ top: 47, bottom: 34, left: 0, right: 0 });

    const { getByTestId, toJSON } = await render(
      <NavigationContainer>
        <Header />
      </NavigationContainer>
    );

    await fireEvent.press(getByTestId('header-menu-button'));

    const modalNode = findModalNode(toJSON());
    const contentNode = findNodeWithStyleKey(modalNode, 'borderTopLeftRadius');
    expect(contentNode).toBeTruthy();

    const flatStyle = flattenStyle(contentNode.props.style);
    const paddingBottom = Number(flatStyle.paddingBottom ?? 0);

    expect(paddingBottom).toBeGreaterThanOrEqual(34);
    // Nunca deve ficar menor que o espaçamento padrão usado quando não há
    // safe area (ex.: Android sem home indicator).
    expect(paddingBottom).toBeGreaterThanOrEqual(spacing.xl);
  });
});
