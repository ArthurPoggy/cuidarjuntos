import React from 'react';
import { render, screen, waitFor, fireEvent } from '@testing-library/react-native';

jest.setTimeout(20000);

jest.mock('react-native-safe-area-context', () =>
  require('react-native-safe-area-context/jest/mock').default
);

jest.mock('../../api/endpoints', () => ({
  medicationsApi: {
    stockOverview: jest.fn(),
    addStock: jest.fn(),
    create: jest.fn(),
  },
}));

import { medicationsApi } from '../../api/endpoints';
import MedicationStockScreen from '../MedicationStockScreen';

const mockedStockOverview = medicationsApi.stockOverview as jest.Mock;

const buildStockResponse = () => ({
  data: {
    sections: [
      {
        key: 'danger',
        title: 'Estoque Critico',
        items: [
          { id: 1, name: 'Paracetamol', dosage: '500mg', created_at: '2026-01-01', current_stock: 2, status: 'danger' },
        ],
      },
      {
        key: 'ok',
        title: 'Estoque OK',
        items: [
          { id: 2, name: 'Ibuprofeno', dosage: '400mg', created_at: '2026-01-01', current_stock: 30, status: 'ok' },
        ],
      },
    ],
  },
});

describe('MedicationStockScreen', () => {
  beforeEach(() => {
    mockedStockOverview.mockReset();
  });

  it('carrega o estoque a partir da API e renderiza os medicamentos', async () => {
    mockedStockOverview.mockResolvedValueOnce(buildStockResponse());

    render(<MedicationStockScreen />);

    await waitFor(
      () => {
        expect(screen.getByText('Paracetamol')).toBeTruthy();
      },
      { timeout: 10000 }
    );

    expect(screen.getByText('Ibuprofeno')).toBeTruthy();
    expect(screen.getByText('500mg')).toBeTruthy();
    expect(mockedStockOverview).toHaveBeenCalledTimes(1);
  });

  it('exibe mensagem de erro quando a API falha', async () => {
    mockedStockOverview.mockRejectedValueOnce(new Error('network error'));

    render(<MedicationStockScreen />);

    await waitFor(() => {
      expect(screen.getByText('Erro ao carregar estoque de medicamentos.')).toBeTruthy();
    });
  });

  it('busca novamente ao submeter o campo de busca', async () => {
    mockedStockOverview.mockResolvedValue(buildStockResponse());

    render(<MedicationStockScreen />);

    await waitFor(() => {
      expect(screen.getByText('Paracetamol')).toBeTruthy();
    });

    const searchInput = screen.getByPlaceholderText('Buscar medicamento...');
    fireEvent.changeText(searchInput, 'Para');
    fireEvent(searchInput, 'submitEditing');

    await waitFor(() => {
      expect(mockedStockOverview).toHaveBeenCalledTimes(2);
    });
    expect(mockedStockOverview).toHaveBeenLastCalledWith({ search: 'Para' });
  });
});
