import React from 'react';
import { Text } from 'react-native';
import { render } from '@testing-library/react-native';

/**
 * Teste trivial de smoke exigido pela tarefa #110 "Consertar agenda ->
 * MOBILE", item "Preparar infraestrutura de testes automatizados no app
 * mobile".
 *
 * Nao existe hoje nenhuma forma de montar/renderizar um componente React
 * Native de verdade em teste (falta jest-expo + @testing-library/react-native
 * configurados via jest.config.js), entao este arquivo nem chega a ser
 * coletado por `npm test` (nao ha script `test`) nem, se rodado isolado via
 * `npx jest`, consegue ser transformado (falta preset/transform para
 * TSX) — ver src/__tests__/testAutomationInfra.test.ts para o gate que cobre
 * essa lacuna de configuracao.
 *
 * Uma vez que a infraestrutura estiver pronta, este teste apenas garante que
 * a suite consegue renderizar um componente RN simples via
 * @testing-library/react-native sem lancar excecao.
 */
describe('Smoke test da suite de testes do app mobile', () => {
  it('renderiza um componente React Native trivial sem lancar excecao', async () => {
    const { getByText } = await render(<Text>ok</Text>);

    expect(getByText('ok')).toBeTruthy();
  });
});
