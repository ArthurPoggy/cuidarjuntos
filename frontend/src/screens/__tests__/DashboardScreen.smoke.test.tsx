import React from 'react';
import { render, waitFor } from '@testing-library/react-native';
import DashboardScreen from '../DashboardScreen';
import { dashboardApi } from '../../api/endpoints';

/**
 * Teste de smoke exigido pela tarefa #109 "Deixar o dashboard em grid
 * padrao -> MOBILE": "Criar infraestrutura minima de testes automatizados
 * no frontend RN".
 *
 * Monta <DashboardScreen/> com `dashboardApi.get` mockado (nenhuma chamada
 * de rede real) e garante que a tela renderiza sem lancar excecao, exibindo
 * os cards de categoria e os registros retornados pela API mockada.
 *
 * Depende de:
 *  - preset "jest-expo" configurado em jest.config.js (ambiente RN + mocks
 *    de modulos nativos/Expo como expo-secure-store, AsyncStorage, etc.);
 *  - `@testing-library/react-native` instalado;
 *  - `dashboardApi.get` (frontend/src/api/endpoints.ts) mockavel via
 *    `jest.mock`, sem que isso dispare uma chamada HTTP real (axios/client).
 *
 * Ver src/__tests__/dashboardTestInfra.test.ts para o gate que cobre esse
 * gap de configuracao/infra.
 */

jest.mock('../../api/endpoints', () => ({
  dashboardApi: {
    get: jest.fn(),
  },
}));

const mockNavigation = {
  navigate: jest.fn(),
} as any;

const mockDashboardData = {
  counts: {
    medication: 2,
    meal: 1,
  },
  records: [
    {
      id: 1,
      patient: 1,
      type: 'medication',
      what: 'Losartana',
      description: '',
      medication: null,
      capsule_quantity: null,
      progress_trend: '',
      missed_reason: '',
      is_exception: false,
      date: '2026-08-06',
      time: '08:00',
      recurrence: 'none',
      repeat_until: null,
      status: 'pending',
      caregiver: '',
      created_by: null,
      timestamp: '2026-08-06T08:00:00Z',
      recurrence_group: null,
      author_name: 'Cuidador',
    },
  ],
};

describe('DashboardScreen - smoke test', () => {
  beforeEach(() => {
    (dashboardApi.get as jest.Mock).mockReset();
    (dashboardApi.get as jest.Mock).mockResolvedValue({ data: mockDashboardData });
  });

  it('renderiza sem lancar excecao usando dashboardApi mockado', async () => {
    const { toJSON, getByText } = await render(
      <DashboardScreen navigation={mockNavigation} />
    );

    await waitFor(() => {
      expect(toJSON()).not.toBeNull();
    });

    await waitFor(() => {
      expect(dashboardApi.get).toHaveBeenCalled();
    });

    // Registro retornado pela API mockada deve aparecer na tela.
    await waitFor(() => {
      expect(getByText('Losartana')).toBeTruthy();
    });
  });
});
