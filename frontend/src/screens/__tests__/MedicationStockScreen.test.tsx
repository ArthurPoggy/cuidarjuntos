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
          {
            id: 1,
            name: 'Paracetamol',
            dosage: '500mg',
            created_at: '2026-01-01',
            current_stock: 2,
            status: 'danger',
            next_dose: { date: '2026-08-07', time: '08:00' },
          },
        ],
      },
      {
        key: 'ok',
        title: 'Estoque OK',
        items: [
          {
            id: 2,
            name: 'Ibuprofeno',
            dosage: '400mg',
            created_at: '2026-01-01',
            current_stock: 30,
            status: 'ok',
            next_dose: null,
          },
        ],
      },
    ],
  },
});

const buildEmptyResponse = () => ({
  data: { sections: [] },
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

  it('exibe o proximo horario do medicamento quando next_dose esta presente', async () => {
    mockedStockOverview.mockResolvedValueOnce(buildStockResponse());

    render(<MedicationStockScreen />);

    await waitFor(() => {
      expect(screen.getByText('Paracetamol')).toBeTruthy();
    });

    // Paracetamol tem next_dose preenchido: o horario "08:00" deve aparecer no card.
    expect(screen.getByText(/08:00/)).toBeTruthy();
    expect(screen.getByTestId('med-next-dose-1')).toBeTruthy();
  });

  it('omite o bloco de proximo horario sem quebrar o card quando next_dose e null', async () => {
    mockedStockOverview.mockResolvedValueOnce(buildStockResponse());

    render(<MedicationStockScreen />);

    await waitFor(() => {
      expect(screen.getByText('Ibuprofeno')).toBeTruthy();
    });

    // Ibuprofeno tem next_dose null: nenhum bloco de horario deve ser renderizado para ele,
    // e o restante do card (nome, dosagem, estoque) continua presente.
    expect(screen.queryByTestId('med-next-dose-2')).toBeNull();
    expect(screen.getByText('Ibuprofeno')).toBeTruthy();
    expect(screen.getByText('400mg')).toBeTruthy();
    expect(screen.getByText('30')).toBeTruthy();
  });

  it('mostra mensagem de "nenhum remedio cadastrado" quando a lista esta vazia sem busca', async () => {
    mockedStockOverview.mockResolvedValueOnce(buildEmptyResponse());

    render(<MedicationStockScreen />);

    await waitFor(() => {
      expect(screen.getByText(/nenhum medicamento cadastrado/i)).toBeTruthy();
    });

    expect(screen.queryByText(/nenhum resultado/i)).toBeNull();
  });

  it('mostra mensagem de "nenhum resultado" quando a busca preenchida nao encontra nada', async () => {
    mockedStockOverview.mockResolvedValue(buildEmptyResponse());

    render(<MedicationStockScreen />);

    await waitFor(() => {
      expect(screen.getByText(/nenhum medicamento cadastrado/i)).toBeTruthy();
    });

    const searchInput = screen.getByPlaceholderText('Buscar medicamento...');
    fireEvent.changeText(searchInput, 'Inexistente');
    fireEvent(searchInput, 'submitEditing');

    await waitFor(() => {
      expect(mockedStockOverview).toHaveBeenCalledTimes(2);
    });

    expect(screen.getByText(/nenhum resultado/i)).toBeTruthy();
    expect(screen.queryByText(/nenhum medicamento cadastrado/i)).toBeNull();
  });
});
