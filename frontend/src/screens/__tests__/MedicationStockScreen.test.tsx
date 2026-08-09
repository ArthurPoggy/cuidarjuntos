import React from 'react';
import { Alert } from 'react-native';
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
    update: jest.fn(),
    delete: jest.fn(),
  },
}));

import { medicationsApi } from '../../api/endpoints';
import MedicationStockScreen from '../MedicationStockScreen';

const mockedStockOverview = medicationsApi.stockOverview as jest.Mock;
const mockedUpdate = medicationsApi.update as jest.Mock;
const mockedDelete = medicationsApi.delete as jest.Mock;

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

    await render(<MedicationStockScreen />);

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

    await render(<MedicationStockScreen />);

    await waitFor(() => {
      expect(screen.getByText('Erro ao carregar estoque de medicamentos.')).toBeTruthy();
    });
  });

  it('busca novamente ao submeter o campo de busca', async () => {
    mockedStockOverview.mockResolvedValue(buildStockResponse());

    await render(<MedicationStockScreen />);

    await waitFor(() => {
      expect(screen.getByText('Paracetamol')).toBeTruthy();
    });

    const searchInput = screen.getByPlaceholderText('Buscar medicamento...');
    await fireEvent.changeText(searchInput, 'Para');

    // Aguarda o estado do campo de busca ser aplicado antes de submeter,
    // como aconteceria digitando de verdade (eventos em ticks separados).
    await waitFor(() => {
      expect(screen.getByPlaceholderText('Buscar medicamento...').props.value).toBe('Para');
    });

    await fireEvent(searchInput, 'submitEditing');

    await waitFor(() => {
      expect(mockedStockOverview).toHaveBeenCalledTimes(2);
    });
    expect(mockedStockOverview).toHaveBeenLastCalledWith({ search: 'Para' });
  });

  it('exibe o proximo horario do medicamento quando next_dose esta presente', async () => {
    mockedStockOverview.mockResolvedValueOnce(buildStockResponse());

    await render(<MedicationStockScreen />);

    await waitFor(() => {
      expect(screen.getByText('Paracetamol')).toBeTruthy();
    });

    // Paracetamol tem next_dose preenchido: o horario "08:00" deve aparecer no card.
    expect(screen.getByText(/08:00/)).toBeTruthy();
    expect(screen.getByTestId('med-next-dose-1')).toBeTruthy();
  });

  it('omite o bloco de proximo horario sem quebrar o card quando next_dose e null', async () => {
    mockedStockOverview.mockResolvedValueOnce(buildStockResponse());

    await render(<MedicationStockScreen />);

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

    await render(<MedicationStockScreen />);

    await waitFor(() => {
      expect(screen.getByText(/nenhum medicamento cadastrado/i)).toBeTruthy();
    });

    expect(screen.queryByText(/nenhum resultado/i)).toBeNull();
  });

  it('mostra mensagem de "nenhum resultado" quando a busca preenchida nao encontra nada', async () => {
    mockedStockOverview.mockResolvedValue(buildEmptyResponse());

    await render(<MedicationStockScreen />);

    await waitFor(() => {
      expect(screen.getByText(/nenhum medicamento cadastrado/i)).toBeTruthy();
    });

    const searchInput = screen.getByPlaceholderText('Buscar medicamento...');
    await fireEvent.changeText(searchInput, 'Inexistente');

    await waitFor(() => {
      expect(screen.getByPlaceholderText('Buscar medicamento...').props.value).toBe('Inexistente');
    });

    await fireEvent(searchInput, 'submitEditing');

    await waitFor(() => {
      expect(mockedStockOverview).toHaveBeenCalledTimes(2);
    });

    expect(screen.getByText(/nenhum resultado/i)).toBeTruthy();
    expect(screen.queryByText(/nenhum medicamento cadastrado/i)).toBeNull();
  });

  describe('editar medicamento', () => {
    beforeEach(() => {
      mockedUpdate.mockReset();
    });

    it('abre o modal de edicao pre-preenchido com nome e dosagem ao tocar em editar', async () => {
      mockedStockOverview.mockResolvedValueOnce(buildStockResponse());

      await render(<MedicationStockScreen />);

      await waitFor(() => {
        expect(screen.getByText('Paracetamol')).toBeTruthy();
      });

      await fireEvent.press(screen.getByTestId('med-edit-1'));

      await waitFor(() => {
        expect(screen.getByDisplayValue('Paracetamol')).toBeTruthy();
      });
      expect(screen.getByDisplayValue('500mg')).toBeTruthy();
    });

    it('chama medicationsApi.update com o id e os dados alterados ao confirmar a edicao', async () => {
      mockedStockOverview.mockResolvedValueOnce(buildStockResponse());
      mockedUpdate.mockResolvedValueOnce({ data: {} });
      mockedStockOverview.mockResolvedValueOnce(buildStockResponse());

      await render(<MedicationStockScreen />);

      await waitFor(() => {
        expect(screen.getByText('Paracetamol')).toBeTruthy();
      });

      await fireEvent.press(screen.getByTestId('med-edit-1'));

      await waitFor(() => {
        expect(screen.getByDisplayValue('Paracetamol')).toBeTruthy();
      });

      const nameInput = screen.getByDisplayValue('Paracetamol');
      const dosageInput = screen.getByDisplayValue('500mg');
      await fireEvent.changeText(nameInput, 'Paracetamol Novo');
      await fireEvent.changeText(dosageInput, '750mg');

      await waitFor(() => {
        expect(screen.getByDisplayValue('Paracetamol Novo')).toBeTruthy();
        expect(screen.getByDisplayValue('750mg')).toBeTruthy();
      });

      await fireEvent.press(screen.getByTestId('med-edit-confirm'));

      await waitFor(() => {
        expect(mockedUpdate).toHaveBeenCalledWith(1, {
          name: 'Paracetamol Novo',
          dosage: '750mg',
        });
      });

      // Aguarda o fim completo do fluxo de edicao (inclusive o recarregamento
      // do estoque apos salvar) para nao deixar uma chamada assincrona
      // pendente vazando para o proximo teste.
      await waitFor(() => {
        expect(mockedStockOverview).toHaveBeenCalledTimes(2);
      });
    });
  });

  describe('remover medicamento', () => {
    beforeEach(() => {
      mockedDelete.mockReset();
      jest.spyOn(Alert, 'alert').mockImplementation(() => {});
    });

    afterEach(() => {
      (Alert.alert as jest.Mock).mockRestore();
    });

    it('exibe o ConfirmModal (sem usar Alert.alert) ao tocar em remover', async () => {
      mockedStockOverview.mockResolvedValueOnce(buildStockResponse());

      await render(<MedicationStockScreen />);

      await waitFor(() => {
        expect(screen.getByText('Paracetamol')).toBeTruthy();
      });

      await fireEvent.press(screen.getByTestId('med-remove-1'));

      expect(Alert.alert).not.toHaveBeenCalled();
      expect(screen.getByText('Deseja remover Paracetamol?')).toBeTruthy();
    });

    it('ao cancelar no ConfirmModal, nenhuma chamada de delete e feita', async () => {
      mockedStockOverview.mockResolvedValueOnce(buildStockResponse());

      await render(<MedicationStockScreen />);

      await waitFor(() => {
        expect(screen.getByText('Paracetamol')).toBeTruthy();
      });

      await fireEvent.press(screen.getByTestId('med-remove-1'));

      await waitFor(() => {
        expect(screen.getByText('Deseja remover Paracetamol?')).toBeTruthy();
      });

      await fireEvent.press(screen.getByText('Cancelar'));

      expect(mockedDelete).not.toHaveBeenCalled();
      await waitFor(() => {
        expect(screen.queryByText('Deseja remover Paracetamol?')).toBeNull();
      });
    });

    it('chama medicationsApi.delete com o id correto e remove o item da lista ao confirmar no ConfirmModal', async () => {
      mockedStockOverview.mockResolvedValueOnce(buildStockResponse());
      mockedDelete.mockResolvedValueOnce({ data: {} });
      // Apos a exclusao, a tela deve recarregar o estoque sem o item removido.
      mockedStockOverview.mockResolvedValueOnce({
        data: {
          sections: [
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

      await render(<MedicationStockScreen />);

      await waitFor(() => {
        expect(screen.getByText('Paracetamol')).toBeTruthy();
      });

      await fireEvent.press(screen.getByTestId('med-remove-1'));

      await waitFor(() => {
        expect(screen.getByText('Deseja remover Paracetamol?')).toBeTruthy();
      });

      await fireEvent.press(screen.getByTestId('confirm-modal-confirm-button'));

      await waitFor(() => {
        expect(mockedDelete).toHaveBeenCalledWith(1);
      });

      await waitFor(() => {
        expect(screen.queryByText('Paracetamol')).toBeNull();
      });
      expect(screen.getByText('Ibuprofeno')).toBeTruthy();
    });

    it('exibe Alert.alert de erro quando a remocao falha, sem regressao', async () => {
      mockedStockOverview.mockResolvedValueOnce(buildStockResponse());
      mockedDelete.mockRejectedValueOnce(new Error('network error'));

      await render(<MedicationStockScreen />);

      await waitFor(() => {
        expect(screen.getByText('Paracetamol')).toBeTruthy();
      });

      await fireEvent.press(screen.getByTestId('med-remove-1'));

      await waitFor(() => {
        expect(screen.getByText('Deseja remover Paracetamol?')).toBeTruthy();
      });

      await fireEvent.press(screen.getByTestId('confirm-modal-confirm-button'));

      await waitFor(() => {
        expect(Alert.alert).toHaveBeenCalledWith(
          'Erro',
          'Nao foi possivel remover o medicamento.'
        );
      });
    });
  });

  describe('layout responsivo com textos longos', () => {
    const LONG_NAME =
      'Cloridrato de Propranolol Associado a Hidroclorotiazida Comprimidos Revestidos Uso Continuo';
    const LONG_DOSAGE =
      '80mg + 25mg - Tomar dois comprimidos por via oral a cada doze horas durante o tratamento continuo';

    const buildLongTextResponse = () => ({
      data: {
        sections: [
          {
            key: 'ok',
            title: 'Estoque OK',
            items: [
              {
                id: 3,
                name: LONG_NAME,
                dosage: LONG_DOSAGE,
                created_at: '2026-01-01',
                current_stock: 10,
                status: 'ok',
                next_dose: null,
              },
            ],
          },
        ],
      },
    });

    it('renderiza o card sem lancar erro quando nome e dosagem sao muito longos (80+ caracteres)', async () => {
      mockedStockOverview.mockResolvedValueOnce(buildLongTextResponse());

      await expect(render(<MedicationStockScreen />)).resolves.not.toThrow();

      await waitFor(() => {
        expect(screen.getByText(LONG_NAME)).toBeTruthy();
      });
      expect(screen.getByText(LONG_DOSAGE)).toBeTruthy();
    });

    it('aplica numberOfLines/estilo de truncamento previsivel ao nome do medicamento', async () => {
      mockedStockOverview.mockResolvedValueOnce(buildLongTextResponse());

      await render(<MedicationStockScreen />);

      const nameEl = await screen.findByText(LONG_NAME);

      // O nome deve ser limitado a um numero fixo de linhas (nao pode crescer sem limite
      // e empurrar os botoes de acao para fora da tela).
      expect(nameEl.props.numberOfLines).toBeGreaterThanOrEqual(1);

      const flattenedStyle = [nameEl.props.style].flat();
      const hasShrinkStyle = flattenedStyle.some(
        (s) => s && (s.flexShrink === 1 || s.flexShrink === true)
      );
      expect(hasShrinkStyle).toBe(true);
    });

    it('aplica numberOfLines/estilo de truncamento previsivel a dosagem do medicamento', async () => {
      mockedStockOverview.mockResolvedValueOnce(buildLongTextResponse());

      await render(<MedicationStockScreen />);

      const dosageEl = await screen.findByText(LONG_DOSAGE);

      expect(dosageEl.props.numberOfLines).toBeGreaterThanOrEqual(1);

      const flattenedStyle = [dosageEl.props.style].flat();
      const hasShrinkStyle = flattenedStyle.some(
        (s) => s && (s.flexShrink === 1 || s.flexShrink === true)
      );
      expect(hasShrinkStyle).toBe(true);
    });

    it('mantem os botoes de acao (Editar, Remover, + Estoque) visiveis mesmo com textos longos', async () => {
      mockedStockOverview.mockResolvedValueOnce(buildLongTextResponse());

      await render(<MedicationStockScreen />);

      await waitFor(() => {
        expect(screen.getByText(LONG_NAME)).toBeTruthy();
      });

      expect(screen.getByTestId('med-edit-3')).toBeTruthy();
      expect(screen.getByTestId('med-remove-3')).toBeTruthy();
      expect(screen.getByText('+ Estoque')).toBeTruthy();
    });
  });
});
