import React from 'react';
import { render, waitFor } from '@testing-library/react-native';
import { Platform } from 'react-native';
import DashboardScreen from '../DashboardScreen';
import { dashboardApi } from '../../api/endpoints';
import { RECORD_TYPES } from '../../utils/constants';

/**
 * Tarefa #109 "Deixar o dashboard em grid padrao -> MOBILE": item
 * "Validar zero erros de TypeScript e ausencia de quebras de renderizacao
 * em iOS/Android".
 *
 * A store `gridTemplateColumns` usada hoje pelo grid de CategoryCard em
 * DashboardScreen (`{ gridTemplateColumns: ... } as any`) e uma propriedade
 * CSS web-only, injetada via `as any` para escapar do typecheck do
 * StyleSheet do React Native. Isso e aceitavel *desde que* nao quebre a
 * renderizacao nativa (iOS/Android), onde essa propriedade simplesmente nao
 * existe no RN StyleSheet e deve ser ignorada silenciosamente pelo runtime
 * nativo (nao ha branch algum em DashboardScreen/CategoryCard hoje que leia
 * `Platform.OS`; o objetivo deste teste e travar essa premissa como
 * regressao futura).
 *
 * Este teste troca `Platform.OS` (objeto singleton exportado por
 * 'react-native', mutavel via atribuicao direta na propriedade de dados
 * `OS`) para 'ios' e depois para 'android' e, para AMBAS as plataformas,
 * monta <DashboardScreen/> (com `dashboardApi.get` mockado, sem chamada de
 * rede real) e confirma que:
 *   - montar o componente nao lanca excecao;
 *   - a quantidade de nodes com a assinatura de estilo do CategoryCard
 *     (`minHeight: 120` + `borderWidth: 2`, exclusiva de
 *     components/CategoryCard.tsx) e igual a RECORD_TYPES.length.
 *
 * Optou-se por mutar `Platform.OS` diretamente (em vez de
 * `jest.resetModules()` + `require` fresco de DashboardScreen a cada
 * iteracao) porque `jest.resetModules()` cria uma NOVA instancia do modulo
 * 'react' a cada reset, dessincronizada da instancia usada por
 * react-test-renderer/@testing-library carregada estaticamente no topo do
 * arquivo -- o que quebra qualquer hook (`Cannot read properties of null
 * (reading 'useState')`), independente do bug real que este teste quer
 * cobrir.
 *
 * Este arquivo tambem roda `npx tsc --noEmit` (exatamente o comando do
 * criterio de aceite da tarefa) e confirma exit code 0, sem nenhuma linha
 * "error TS" na saida — cobrindo a parte "zero erros de TypeScript" do
 * mesmo item.
 */

jest.mock('../../api/endpoints', () => ({
  dashboardApi: {
    get: jest.fn(),
  },
}));

const mockNavigation = { navigate: jest.fn() } as any;

const mockDashboardData = {
  counts: {},
  records: [],
};

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
 * Percorre a arvore JSON (react-test-renderer) renderizada e conta quantos
 * nodes tem o style "assinatura" do card interno de CategoryCard
 * (`styles.card` em components/CategoryCard.tsx: `minHeight: 120` +
 * `borderWidth: 2`, combinacao exclusiva desse componente na tela). Usado
 * como proxy independente de plataforma para "quantos CategoryCard foram
 * renderizados", sem depender de APIs de introspeccao de tipo de
 * componente que podem nao existir em toda versao do
 * @testing-library/react-native.
 */
function countCategoryCardNodes(node: any): number {
  if (!node || typeof node !== 'object') return 0;

  let count = 0;
  const flattened = flattenStyle(node.props && node.props.style);
  if (flattened.minHeight === 120 && flattened.borderWidth === 2) {
    count += 1;
  }

  if (Array.isArray(node.children)) {
    for (const child of node.children) {
      count += countCategoryCardNodes(child);
    }
  }

  return count;
}

describe('DashboardScreen - renderizacao nativa (iOS/Android)', () => {
  const originalPlatformOS = Platform.OS;

  beforeEach(() => {
    (dashboardApi.get as jest.Mock).mockReset();
    (dashboardApi.get as jest.Mock).mockResolvedValue({ data: mockDashboardData });
  });

  afterEach(() => {
    (Platform as any).OS = originalPlatformOS;
  });

  it.each(['ios', 'android'] as const)(
    'com Platform.OS = %s, renderiza sem excecao e com um CategoryCard por RECORD_TYPES',
    async (platformOS) => {
      (Platform as any).OS = platformOS;
      expect(Platform.OS).toBe(platformOS);

      let renderError: unknown = null;
      let renderResult: Awaited<ReturnType<typeof render>> | undefined;

      try {
        renderResult = await render(<DashboardScreen navigation={mockNavigation} />);
      } catch (err) {
        renderError = err;
      }

      expect(renderError).toBeNull();

      await waitFor(() => {
        expect(renderResult!.toJSON()).not.toBeNull();
      });

      const categoryCardCount = countCategoryCardNodes(renderResult!.toJSON());
      expect(categoryCardCount).toBe(RECORD_TYPES.length);
    }
  );
});

describe('Zero erros de TypeScript no frontend (npx tsc --noEmit)', () => {
  it('"npx tsc --noEmit" termina com exit code 0 e sem nenhuma linha "error TS"', () => {
    const path = require('path');
    const { execSync } = require('child_process');
    const FRONTEND_ROOT = path.resolve(__dirname, '..', '..', '..');

    let output = '';
    let exitCode = 0;

    try {
      output = execSync('npx tsc --noEmit', {
        cwd: FRONTEND_ROOT,
        encoding: 'utf-8',
        stdio: ['ignore', 'pipe', 'pipe'],
      });
    } catch (err) {
      const execErr = err as { status?: number; stdout?: string; stderr?: string };
      exitCode = execErr.status ?? 1;
      output = `${execErr.stdout ?? ''}${execErr.stderr ?? ''}`;
    }

    const hasTsErrorLine = /error TS\d+/.test(output);

    expect({ exitCode, hasTsErrorLine }).toEqual(
      expect.objectContaining({ exitCode: 0, hasTsErrorLine: false })
    );
  }, 120000);
});
