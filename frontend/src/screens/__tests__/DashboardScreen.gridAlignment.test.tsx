import React from 'react';
import { render, waitFor } from '@testing-library/react-native';
import * as ReactNative from 'react-native';
import DashboardScreen from '../DashboardScreen';
import { dashboardApi } from '../../api/endpoints';
import { spacing } from '../../theme';

/**
 * Tarefa #109 "Deixar o dashboard em grid padrao -> MOBILE": item
 * "Padronizar espacamento e alinhamento dos CategoryCards no grid (inclui
 * casos de poucos/muitos cards)".
 *
 * O wrapper de cada CategoryCard (`categoryCardWrapper` em DashboardScreen)
 * hoje define apenas `padding: spacing.xs` (via StyleSheet) e `width:
 * '${100 / numColumns}%'` (inline, por item). Isso NAO garante gutters
 * consistentes: nao ha `flexBasis`/`maxWidth` fixando a caixa do item nas
 * proporcoes do grid, entao o alinhamento da ultima linha (quando o total
 * de RECORD_TYPES nao e multiplo de numColumns) fica sujeito ao
 * comportamento padrao de `flexWrap` do container, sem nenhuma garantia
 * estrutural de que a largura de caixa (box) de cada card e identica em
 * qualquer resto de divisao.
 *
 * Este teste mocka `RECORD_TYPES` (via '../../utils/constants') para
 * tamanhos 1, 2, 5 e 7 com numColumns fixo em 3 (largura de janela
 * desktop, >=1024) e verifica, para cada wrapper de CategoryCard
 * renderizado:
 *   - largura igual a `100/numColumns%` (nenhum wrapper fora do padrao);
 *   - mesmo padding (`spacing.xs`) em todos os wrappers;
 *   - `flexBasis` e `maxWidth` explicitos e iguais entre si, travando a
 *     caixa do item independentemente da linha (inclusive a ultima linha
 *     incompleta) - hoje ausentes no wrapper, entao estas asserts falham
 *     mesmo quando a contagem de itens e multiplo de numColumns (1 coluna
 *     usada por todos os cards) porque a propriedade simplesmente nao
 *     existe no style computado.
 *
 * Contra o codigo atual, `categoryCardWrapper` nao define `flexBasis` nem
 * `maxWidth`, entao os asserts de `flexBasis`/`maxWidth` devem falhar de
 * forma clara (valor `undefined` != valor esperado).
 */

jest.mock('../../api/endpoints', () => ({
  dashboardApi: {
    get: jest.fn(),
  },
}));

// Mocka o modulo de constants preservando tudo (CATEGORY_META, etc.), mas
// tornando `RECORD_TYPES` um array MUTAVEL que os testes podem repopular
// (via splice, nao reassign) para simular 1/2/5/7 tipos de registro sem
// precisar de `jest.resetModules()` (que quebraria o singleton do React
// usado pelo react-test-renderer).
jest.mock('../../utils/constants', () => {
  const actual = jest.requireActual('../../utils/constants');
  return {
    ...actual,
    RECORD_TYPES: [...actual.RECORD_TYPES],
  };
});

// eslint-disable-next-line @typescript-eslint/no-var-requires
const constantsMock = require('../../utils/constants');
const { RECORD_TYPES: actualRecordTypes } = jest.requireActual('../../utils/constants');

function setMockedRecordTypes(types: string[]) {
  constantsMock.RECORD_TYPES.splice(0, constantsMock.RECORD_TYPES.length, ...types);
}

const mockUseWindowDimensions = jest.spyOn(ReactNative, 'useWindowDimensions');

const mockNavigation = { navigate: jest.fn() } as any;

const mockDashboardData = {
  counts: {},
  records: [],
};

const NUM_COLUMNS = 3;
const DESKTOP_WIDTH = 1200; // >=1024 => getDashboardColumns(width) === 3

/**
 * Flattens a style prop (object or array of objects/falsy) into a single
 * merged plain object, mimicking RN's own style flattening.
 */
function flattenStyle(style: any): Record<string, any> {
  if (!style) return {};
  if (Array.isArray(style)) {
    return style.reduce((acc, s) => ({ ...acc, ...flattenStyle(s) }), {});
  }
  return style;
}

/**
 * Percorre a arvore JSON (react-test-renderer) renderizada e coleta o
 * style computado (flattened) de todo node cujo style contenha um `width`
 * percentual (formato usado pelo wrapper de CategoryCard, ex.:
 * "33.333...%").
 */
function collectCategoryWrapperStyles(node: any, acc: Record<string, any>[] = []): Record<string, any>[] {
  if (!node || typeof node !== 'object') return acc;

  const style = node.props && node.props.style;
  if (style) {
    const flattened = flattenStyle(style);
    if (typeof flattened.width === 'string' && flattened.width.endsWith('%')) {
      acc.push(flattened);
    }
  }

  if (Array.isArray(node.children)) {
    for (const child of node.children) {
      collectCategoryWrapperStyles(child, acc);
    }
  }

  return acc;
}

describe('DashboardScreen - alinhamento/espacamento do grid de CategoryCards', () => {
  beforeEach(() => {
    (dashboardApi.get as jest.Mock).mockReset();
    (dashboardApi.get as jest.Mock).mockResolvedValue({ data: mockDashboardData });
    mockUseWindowDimensions.mockReset();
    mockUseWindowDimensions.mockReturnValue({
      width: DESKTOP_WIDTH,
      height: 800,
      scale: 2,
      fontScale: 1,
    });
  });

  afterEach(() => {
    // Restaura RECORD_TYPES completo para nao vazar estado entre testes.
    setMockedRecordTypes(actualRecordTypes);
  });

  it.each([1, 2, 5, 7])(
    'com %i CategoryCard(s) em numColumns=3, todos os wrappers tem a mesma largura, padding, flexBasis e maxWidth',
    async (numItems) => {
      const mockedTypes = Array.from(
        { length: numItems },
        (_, i) => actualRecordTypes[i % actualRecordTypes.length]
      );
      setMockedRecordTypes(mockedTypes);

      const { toJSON } = await render(
        <DashboardScreen navigation={mockNavigation} />
      );

      await waitFor(() => {
        expect(dashboardApi.get).toHaveBeenCalled();
      });

      const wrapperStyles = collectCategoryWrapperStyles(toJSON());
      const expectedWidth = `${100 / NUM_COLUMNS}%`;

      // Um wrapper por CategoryCard renderizado.
      expect(wrapperStyles.length).toBe(numItems);

      for (const style of wrapperStyles) {
        // Largura sempre igual a 100/numColumns, nenhum wrapper fora do
        // padrao (inclusive na ultima linha incompleta).
        expect(style.width).toBe(expectedWidth);

        // Mesmo padding (spacing.xs) em todos os wrappers.
        expect(style.padding).toBe(spacing.xs);

        // Caixa do item travada de forma consistente: flexBasis e maxWidth
        // devem existir e ser iguais a largura esperada, garantindo gutter
        // consistente independentemente do resto da divisao de itens por
        // numColumns.
        expect(style.flexBasis).toBe(expectedWidth);
        expect(style.maxWidth).toBe(expectedWidth);
      }

      // Todos os wrappers devem ter exatamente o mesmo style (mesma
      // largura/padding/flexBasis/maxWidth), sem excecao para o(s)
      // ultimo(s) item(ns) de uma linha incompleta.
      const uniqueStyleStrings = new Set(
        wrapperStyles.map((s) =>
          JSON.stringify({
            width: s.width,
            padding: s.padding,
            flexBasis: s.flexBasis,
            maxWidth: s.maxWidth,
          })
        )
      );
      expect(uniqueStyleStrings.size).toBe(1);
    }
  );
});
