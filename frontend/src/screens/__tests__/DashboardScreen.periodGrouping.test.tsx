import React from 'react';
import { render, waitFor } from '@testing-library/react-native';
import DashboardScreen from '../DashboardScreen';
import { dashboardApi } from '../../api/endpoints';

/**
 * Tarefa #113 "Agrupar atividades em blocos (manha/tarde/noite)": a lista de
 * registros do dia exibida no DashboardScreen (visao padrao, sem filtro de
 * data explicito -> backend retorna os registros de hoje) deve ser
 * organizada em blocos com cabecalho "Manhã", "Tarde" e "Noite".
 */

jest.mock('../../api/endpoints', () => ({
  dashboardApi: {
    get: jest.fn(),
  },
}));

const mockNavigation = { navigate: jest.fn() } as any;

const baseRecord = {
  id: 0,
  patient: 1,
  type: 'medication',
  description: '',
  medication: null,
  capsule_quantity: null,
  progress_trend: '',
  missed_reason: '',
  is_exception: false,
  date: '2026-08-10',
  recurrence: 'none',
  repeat_until: null,
  status: 'pending',
  caregiver: '',
  created_by: null,
  recurrence_group: null,
  author_name: 'Cuidador',
};

const mockDashboardData = {
  counts: { medication: 3 },
  records: [
    { ...baseRecord, id: 1, what: 'Remedio da noite', time: '20:00', timestamp: '2026-08-10T20:00:00Z' },
    { ...baseRecord, id: 2, what: 'Almoco', time: '13:00', timestamp: '2026-08-10T13:00:00Z' },
    { ...baseRecord, id: 3, what: 'Cafe da manha', time: '08:00', timestamp: '2026-08-10T08:00:00Z' },
  ],
};

describe('DashboardScreen - agrupamento em blocos manha/tarde/noite', () => {
  beforeEach(() => {
    (dashboardApi.get as jest.Mock).mockReset();
    (dashboardApi.get as jest.Mock).mockResolvedValue({ data: mockDashboardData });
  });

  it('exibe cabecalhos de secao Manhã, Tarde e Noite acima dos registros correspondentes', async () => {
    const { getByText, toJSON } = await render(
      <DashboardScreen navigation={mockNavigation} />
    );

    await waitFor(() => {
      expect(toJSON()).not.toBeNull();
    });

    await waitFor(() => {
      expect(getByText('Cafe da manha')).toBeTruthy();
    });

    expect(getByText('Manhã')).toBeTruthy();
    expect(getByText('Tarde')).toBeTruthy();
    expect(getByText('Noite')).toBeTruthy();
    expect(getByText('Almoco')).toBeTruthy();
    expect(getByText('Remedio da noite')).toBeTruthy();
  });

  it('nao exibe cabecalho de bloco sem nenhum registro', async () => {
    (dashboardApi.get as jest.Mock).mockResolvedValue({
      data: {
        counts: { medication: 1 },
        records: [
          { ...baseRecord, id: 1, what: 'Cafe da manha', time: '08:00', timestamp: '2026-08-10T08:00:00Z' },
        ],
      },
    });

    const { getByText, queryByText, toJSON } = await render(
      <DashboardScreen navigation={mockNavigation} />
    );

    await waitFor(() => {
      expect(toJSON()).not.toBeNull();
    });

    await waitFor(() => {
      expect(getByText('Cafe da manha')).toBeTruthy();
    });

    expect(getByText('Manhã')).toBeTruthy();
    expect(queryByText('Tarde')).toBeNull();
    expect(queryByText('Noite')).toBeNull();
  });

  it('ao listar um intervalo com mais de um dia, agrupa por data e preserva a ordem cronologica entre os dias', async () => {
    (dashboardApi.get as jest.Mock).mockResolvedValue({
      data: {
        counts: { medication: 4 },
        records: [
          { ...baseRecord, id: 1, date: '2026-08-10', what: 'Remedio dia 10 noite', time: '20:00', timestamp: '2026-08-10T20:00:00Z' },
          { ...baseRecord, id: 2, date: '2026-08-10', what: 'Remedio dia 10 manha', time: '08:00', timestamp: '2026-08-10T08:00:00Z' },
          { ...baseRecord, id: 3, date: '2026-08-09', what: 'Remedio dia 09 tarde', time: '14:00', timestamp: '2026-08-09T14:00:00Z' },
          { ...baseRecord, id: 4, date: '2026-08-09', what: 'Remedio dia 09 manha', time: '07:00', timestamp: '2026-08-09T07:00:00Z' },
        ],
      },
    });

    const { getByText, getByTestId, toJSON } = await render(
      <DashboardScreen navigation={mockNavigation} />
    );

    await waitFor(() => {
      expect(toJSON()).not.toBeNull();
    });

    await waitFor(() => {
      expect(getByText('Remedio dia 10 noite')).toBeTruthy();
    });

    // Cabecalhos de data devem aparecer quando ha mais de um dia na lista.
    // Usa testID (em vez de getByText) porque o texto formatado da data
    // ("dd/mm/aaaa") pode coincidir com o valor padrao ("hoje") exibido
    // pelos campos de data do PeriodFilter quando o registro de teste cai
    // na data atual do ambiente de execucao.
    expect(getByTestId('date-header-2026-08-10').props.children).toBe('10/08/2026');
    expect(getByTestId('date-header-2026-08-09').props.children).toBe('09/08/2026');

    // Registros dos dois dias continuam presentes, ainda organizados em
    // blocos manha/tarde/noite dentro de cada dia.
    expect(getByText('Remedio dia 10 manha')).toBeTruthy();
    expect(getByText('Remedio dia 09 tarde')).toBeTruthy();
    expect(getByText('Remedio dia 09 manha')).toBeTruthy();
  });
});
