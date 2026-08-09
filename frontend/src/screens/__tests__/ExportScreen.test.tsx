import React from 'react';
import { render, fireEvent, waitFor } from '@testing-library/react-native';

/**
 * Testes automatizados para a tarefa #79 "Filtrar exportacao por categoria de
 * cuidado", subtask 1: criar a tela ExportScreen.
 *
 * Critérios de aceitação cobertos aqui:
 *  - A tela renderiza sem quebrar e expõe um botão "Exportar CSV".
 *  - Permite escolher um intervalo de datas (inicio/fim), reaproveitando o
 *    componente ../components/DateTimePicker com os labels "Data Inicial" e
 *    "Data Final" (mesmo padrão já usado em PeriodFilter.tsx).
 *  - O botão "Exportar CSV" chama dashboardApi.exportCsv passando os params
 *    'start' e 'end' (formato YYYY-MM-DD) quando as datas foram preenchidas,
 *    e sem esses params quando não foram.
 */

jest.mock('../../api/endpoints', () => ({
  dashboardApi: {
    exportCsv: jest.fn(() => Promise.resolve({ data: {} })),
  },
}));

// O widget nativo de data é irrelevante para o fluxo testado aqui; troca por
// um TouchableOpacity simples que, ao ser pressionado, dispara onChange com
// uma data fixa e previsível — mesma técnica usada em
// RecordCreateScreen.medication.test.tsx.
jest.mock('../../components/DateTimePicker', () => {
  const { TouchableOpacity, Text } = require('react-native');
  const React = require('react');
  return function MockDateTimePicker({ label, onChange }: { label: string; onChange: (d: Date) => void }) {
    const fixedDate = label.includes('Inicial') ? new Date(2026, 7, 1) : new Date(2026, 7, 15);
    return (
      <TouchableOpacity testID={`datetimepicker-${label}`} onPress={() => onChange(fixedDate)}>
        <Text>{label}</Text>
      </TouchableOpacity>
    );
  };
});

import { dashboardApi } from '../../api/endpoints';
import { RECORD_TYPES, CATEGORY_META } from '../../utils/constants';
import ExportScreen from '../ExportScreen';

const mockedExportCsv = dashboardApi.exportCsv as jest.Mock;

describe('ExportScreen', () => {
  beforeEach(() => {
    mockedExportCsv.mockReset();
    mockedExportCsv.mockResolvedValue({ data: {} });
  });

  it('renderiza sem lançar erro e exibe o botão "Exportar CSV"', async () => {
    const { getByText } = await render(<ExportScreen />);
    expect(getByText('Exportar CSV')).toBeTruthy();
  });

  it('exibe seletores de data inicial e final', async () => {
    const { getByTestId } = await render(<ExportScreen />);
    expect(getByTestId('datetimepicker-Data Inicial')).toBeTruthy();
    expect(getByTestId('datetimepicker-Data Final')).toBeTruthy();
  });

  it('chama dashboardApi.exportCsv com os params start e end quando as datas foram preenchidas', async () => {
    const { getByTestId, getByText } = await render(<ExportScreen />);

    await fireEvent.press(getByTestId('datetimepicker-Data Inicial'));
    await fireEvent.press(getByTestId('datetimepicker-Data Final'));
    await fireEvent.press(getByText('Exportar CSV'));

    await waitFor(() => {
      expect(mockedExportCsv).toHaveBeenCalledTimes(1);
    });
    expect(mockedExportCsv).toHaveBeenCalledWith({ start: '2026-08-01', end: '2026-08-15' });
  });

  it('chama dashboardApi.exportCsv sem params start/end quando nenhuma data foi selecionada', async () => {
    const { getByText } = await render(<ExportScreen />);

    await fireEvent.press(getByText('Exportar CSV'));

    await waitFor(() => {
      expect(mockedExportCsv).toHaveBeenCalledTimes(1);
    });
    const callArgs = (mockedExportCsv.mock.calls[0][0] || {}) as Record<string, string>;
    expect(callArgs.start).toBeUndefined();
    expect(callArgs.end).toBeUndefined();
  });

  it('exibe um card por categoria (todos os RecordTypes) com label e ícone de CATEGORY_META', async () => {
    const { getByText } = await render(<ExportScreen />);

    expect(RECORD_TYPES.length).toBeGreaterThan(0);
    for (const type of RECORD_TYPES) {
      const meta = CATEGORY_META[type];
      expect(getByText(meta.label)).toBeTruthy();
      expect(getByText(meta.icon)).toBeTruthy();
    }
  });

  it('chama dashboardApi.exportCsv com params.categories igual às categorias selecionadas unidas por vírgula', async () => {
    const { getByText } = await render(<ExportScreen />);

    await fireEvent.press(getByText('Remédio'));
    await fireEvent.press(getByText('Alimentação'));
    await fireEvent.press(getByText('Exportar CSV'));

    await waitFor(() => {
      expect(mockedExportCsv).toHaveBeenCalledTimes(1);
    });
    const callArgs = mockedExportCsv.mock.calls[0][0] as Record<string, string>;
    expect(callArgs.categories).toBe('medication,meal');
  });

  it('desselecionar uma categoria remove ela do params.categories enviado', async () => {
    const { getByText } = await render(<ExportScreen />);

    await fireEvent.press(getByText('Remédio'));
    await fireEvent.press(getByText('Alimentação'));
    await fireEvent.press(getByText('Remédio'));
    await fireEvent.press(getByText('Exportar CSV'));

    await waitFor(() => {
      expect(mockedExportCsv).toHaveBeenCalledTimes(1);
    });
    const callArgs = mockedExportCsv.mock.calls[0][0] as Record<string, string>;
    expect(callArgs.categories).toBe('meal');
  });

  it('não envia params.categories quando nenhuma categoria está selecionada', async () => {
    const { getByText } = await render(<ExportScreen />);

    await fireEvent.press(getByText('Exportar CSV'));

    await waitFor(() => {
      expect(mockedExportCsv).toHaveBeenCalledTimes(1);
    });
    const callArgs = (mockedExportCsv.mock.calls[0][0] || {}) as Record<string, string>;
    expect(callArgs.categories).toBeUndefined();
  });
});
