import React from 'react';
import { render, waitFor, act } from '@testing-library/react-native';
import * as ReactNative from 'react-native';
import DashboardScreen from '../DashboardScreen';
import { dashboardApi } from '../../api/endpoints';
import { RECORD_TYPES } from '../../utils/constants';

/**
 * Tarefa #109 "Deixar o dashboard em grid padrao -> MOBILE":
 * "Extrair calculo de colunas do grid para funcao pura e torna-lo
 * responsivo em runtime".
 *
 * Este teste mocka `useWindowDimensions` (react-native) e confirma que,
 * ao mudar a largura da janela SEM remontar o componente (apenas
 * re-render), o numero de colunas do grid de CategoryCard muda de 1
 * (mobile, largura 400) para 3 (desktop, largura 1200).
 *
 * Contra o codigo atual, `numColumns` e derivado uma unica vez de
 * `Dimensions.get('window')` no escopo do modulo (nao usa
 * `useWindowDimensions`), entao esta mudanca de mock nao tem efeito algum
 * sobre o layout renderizado e o teste falha.
 */

jest.mock('../../api/endpoints', () => ({
  dashboardApi: {
    get: jest.fn(),
  },
}));

// Mocka apenas `useWindowDimensions` via jest.spyOn, preservando o restante
// do modulo 'react-native' (e todos os mocks nativos ja configurados pelo
// preset jest-expo). Evita reimportar o modulo real via jest.requireActual,
// o que dispararia carregamento de TurboModules nativos indisponiveis no
// ambiente de teste (ex.: DevMenu).
const mockUseWindowDimensions = jest.spyOn(ReactNative, 'useWindowDimensions');

const mockNavigation = { navigate: jest.fn() } as any;

const mockDashboardData = {
  counts: {},
  records: [],
};

/**
 * Percorre a arvore JSON (react-test-renderer) renderizada e coleta todos
 * os valores de `style.width` no formato percentual (ex.: "33.333...%"),
 * usados pelos wrappers de CategoryCard para definir a largura de cada
 * coluna do grid.
 */
function collectWidthPercents(node: any, acc: string[] = []): string[] {
  if (!node || typeof node !== 'object') return acc;

  const style = node.props && node.props.style;
  if (style) {
    const styleList = Array.isArray(style) ? style : [style];
    for (const s of styleList) {
      if (s && typeof s === 'object' && typeof s.width === 'string' && s.width.endsWith('%')) {
        acc.push(s.width);
      }
    }
  }

  if (Array.isArray(node.children)) {
    for (const child of node.children) {
      collectWidthPercents(child, acc);
    }
  }

  return acc;
}

describe('DashboardScreen - grid responsivo em runtime', () => {
  beforeEach(() => {
    (dashboardApi.get as jest.Mock).mockReset();
    (dashboardApi.get as jest.Mock).mockResolvedValue({ data: mockDashboardData });
    mockUseWindowDimensions.mockReset();
  });

  it('recalcula numColumns (1 -> 3) quando a largura da janela muda, sem remount', async () => {
    mockUseWindowDimensions.mockReturnValue({ width: 400, height: 800, scale: 2, fontScale: 1 });

    const view = await render(<DashboardScreen navigation={mockNavigation} />);
    const { rerender } = view;

    await waitFor(() => {
      expect(dashboardApi.get).toHaveBeenCalled();
    });

    let widths = collectWidthPercents(view.toJSON());
    // Em largura mobile (400), deve haver 1 coluna: todo wrapper com 100%.
    expect(widths.length).toBe(RECORD_TYPES.length);
    expect(new Set(widths)).toEqual(new Set(['100%']));

    // Simula mudanca de dimensao da janela (ex.: rotacao / resize), sem
    // desmontar o componente: apenas atualiza o valor do hook mockado e
    // forca um novo render do MESMO componente montado.
    mockUseWindowDimensions.mockReturnValue({ width: 1200, height: 800, scale: 2, fontScale: 1 });

    await act(async () => {
      rerender(<DashboardScreen navigation={mockNavigation} />);
    });

    widths = collectWidthPercents(view.toJSON());
    const expectedDesktopWidth = `${100 / 3}%`;

    expect(widths.length).toBe(RECORD_TYPES.length);
    expect(new Set(widths)).toEqual(new Set([expectedDesktopWidth]));
  });
});
