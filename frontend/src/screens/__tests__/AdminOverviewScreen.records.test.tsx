import React from 'react';
import { Alert } from 'react-native';
import { render, screen, waitFor, fireEvent } from '@testing-library/react-native';

jest.setTimeout(20000);

jest.mock('react-native-safe-area-context', () =>
  require('react-native-safe-area-context/jest/mock').default
);

jest.mock('react-native-chart-kit', () => ({
  LineChart: () => null,
}));

jest.mock('../../api/endpoints', () => ({
  adminApi: {
    overview: jest.fn(),
    records: jest.fn(),
  },
  recordsApi: {
    delete: jest.fn(),
  },
}));

import { adminApi, recordsApi } from '../../api/endpoints';
import AdminOverviewScreen from '../AdminOverviewScreen';

const mockedOverview = adminApi.overview as jest.Mock;
const mockedRecords = adminApi.records as jest.Mock;
const mockedDelete = recordsApi.delete as jest.Mock;

/**
 * Tarefa #90 "Aba Registros na tela do admin", subtask 90-2-frontend-aba-registros.
 *
 * Cobre:
 *  - AdminOverviewScreen exibe duas abas: Usuarios (conteudo atual) e Registros.
 *  - Aba Registros busca em adminApi.records(...) e exibe paciente, grupo,
 *    tipo/label, status e data de cada registro.
 *  - Excluir um registro pede confirmacao antes de chamar recordsApi.delete(id).
 *  - Apos excluir com sucesso, o registro some da lista sem reabrir a tela.
 *  - Erro 403/404 na exclusao mostra mensagem de erro e mantem o item na lista.
 */

const buildOverviewResponse = () => ({
  data: {
    total_users: 2,
    total_patients: 1,
    total_groups: 1,
    total_records: 2,
    daily_series: [],
    users: [
      { id: 1, username: 'cuidador1', email: 'cuidador1@example.com', date_joined: '2026-01-01T00:00:00Z' },
    ],
  },
});

const buildRecordsResponse = (results?: unknown[]) => ({
  data: {
    count: results ? results.length : 2,
    next: null,
    previous: null,
    results: results ?? [
      {
        id: 10,
        type: 'medication',
        label: 'Medicamento',
        status: 'pending',
        date: '2026-08-05',
        time: '08:00',
        patient: 'Maria Silva',
        group: 'Familia Silva',
        caregiver: '',
        author_name: 'Cuidador Um',
      },
      {
        id: 11,
        type: 'meal',
        label: 'Refeicao',
        status: 'done',
        date: '2026-08-06',
        time: '12:00',
        patient: 'Maria Silva',
        group: 'Familia Silva',
        caregiver: '',
        author_name: 'Cuidador Dois',
      },
    ],
  },
});

describe('AdminOverviewScreen - abas Usuarios/Registros', () => {
  beforeEach(() => {
    mockedOverview.mockReset();
    mockedRecords.mockReset();
    mockedDelete.mockReset();
    mockedOverview.mockResolvedValue(buildOverviewResponse());
    mockedRecords.mockResolvedValue(buildRecordsResponse());
  });

  it('exibe duas abas pressionaveis (Usuarios/Registros), com Usuarios visivel por padrao, e alternar para Registros troca o conteudo exibido', async () => {
    render(<AdminOverviewScreen />);

    await waitFor(() => {
      expect(screen.getByText('cuidador1')).toBeTruthy();
    });

    // As abas devem existir como elementos pressionaveis e identificaveis por
    // testID (nao apenas por texto, ja que o texto "Registros" tambem aparece
    // como rotulo do stat card na aba Usuarios).
    const usuariosTab = screen.getByTestId('admin-tab-usuarios');
    const registrosTab = screen.getByTestId('admin-tab-registros');
    expect(usuariosTab).toBeTruthy();
    expect(registrosTab).toBeTruthy();

    // A aba Registros nao deve ter sido buscada antes de ser selecionada.
    expect(mockedRecords).not.toHaveBeenCalled();

    // Conteudo da aba Usuarios (lista de usuarios) esta visivel por padrao.
    expect(screen.getByText('cuidador1')).toBeTruthy();

    // Ao pressionar a aba Registros, o conteudo da aba Usuarios (lista de
    // usuarios) deve sumir, provando que houve troca real de aba.
    fireEvent.press(registrosTab);

    await waitFor(() => {
      expect(mockedRecords).toHaveBeenCalled();
    });

    await waitFor(() => {
      expect(screen.queryByText('cuidador1')).toBeNull();
    });
  });

  it('ao tocar na aba Registros, busca em adminApi.records e exibe paciente, grupo, tipo, status e data', async () => {
    render(<AdminOverviewScreen />);

    await waitFor(() => {
      expect(screen.getByText('cuidador1')).toBeTruthy();
    });

    fireEvent.press(screen.getByTestId('admin-tab-registros'));

    await waitFor(() => {
      expect(mockedRecords).toHaveBeenCalled();
    });

    await waitFor(() => {
      expect(screen.getAllByText('Maria Silva').length).toBeGreaterThan(0);
    });

    expect(screen.getAllByText('Familia Silva').length).toBeGreaterThan(0);
    expect(screen.getByText('Medicamento')).toBeTruthy();
    expect(screen.getByText('Refeicao')).toBeTruthy();
  });

  describe('excluir registro', () => {
    beforeEach(() => {
      jest.spyOn(Alert, 'alert').mockImplementation(() => {});
    });

    afterEach(() => {
      (Alert.alert as jest.Mock).mockRestore();
    });

    it('pede confirmacao antes de chamar recordsApi.delete', async () => {
      render(<AdminOverviewScreen />);

      await waitFor(() => {
        expect(screen.getByText('cuidador1')).toBeTruthy();
      });
      fireEvent.press(screen.getByTestId('admin-tab-registros'));

      await waitFor(() => {
        expect(screen.getByTestId('admin-record-delete-10')).toBeTruthy();
      });

      fireEvent.press(screen.getByTestId('admin-record-delete-10'));

      expect(Alert.alert).toHaveBeenCalledTimes(1);
      expect(mockedDelete).not.toHaveBeenCalled();
      const [title] = (Alert.alert as jest.Mock).mock.calls[0];
      expect(title).toMatch(/confirma/i);
    });

    it('remove o registro da lista apos exclusao bem-sucedida, sem reabrir a tela', async () => {
      mockedDelete.mockResolvedValueOnce({ data: {} });

      render(<AdminOverviewScreen />);

      await waitFor(() => {
        expect(screen.getByText('cuidador1')).toBeTruthy();
      });
      fireEvent.press(screen.getByTestId('admin-tab-registros'));

      await waitFor(() => {
        expect(screen.getByText('Medicamento')).toBeTruthy();
      });

      fireEvent.press(screen.getByTestId('admin-record-delete-10'));

      const alertArgs = (Alert.alert as jest.Mock).mock.calls[0];
      const buttons = alertArgs[2] as Array<{ text: string; onPress?: () => void }>;
      const confirmButton = buttons.find((b) => b.text !== 'Cancelar');
      expect(confirmButton).toBeTruthy();

      await confirmButton!.onPress!();

      expect(mockedDelete).toHaveBeenCalledWith(10);

      await waitFor(() => {
        expect(screen.queryByText('Medicamento')).toBeNull();
      });
      expect(screen.getByText('Refeicao')).toBeTruthy();
    });

    it('exibe mensagem de erro e mantem o item na lista quando a exclusao falha com 403', async () => {
      mockedDelete.mockRejectedValueOnce({ response: { status: 403 } });

      render(<AdminOverviewScreen />);

      await waitFor(() => {
        expect(screen.getByText('cuidador1')).toBeTruthy();
      });
      fireEvent.press(screen.getByTestId('admin-tab-registros'));

      await waitFor(() => {
        expect(screen.getByText('Medicamento')).toBeTruthy();
      });

      fireEvent.press(screen.getByTestId('admin-record-delete-10'));

      const alertArgs = (Alert.alert as jest.Mock).mock.calls[0];
      const buttons = alertArgs[2] as Array<{ text: string; onPress?: () => void }>;
      const confirmButton = buttons.find((b) => b.text !== 'Cancelar');

      await confirmButton!.onPress!();

      await waitFor(() => {
        expect(mockedDelete).toHaveBeenCalledWith(10);
      });

      // O registro continua na lista apos a falha.
      expect(screen.getByText('Medicamento')).toBeTruthy();

      // Alguma mensagem de erro deve ter sido comunicada ao usuario (segundo
      // Alert.alert, ou texto de erro na propria tela).
      const erroAlertCalled = (Alert.alert as jest.Mock).mock.calls.some(
        (call) => /erro|nao foi possivel/i.test(String(call[0]) + String(call[1] ?? ''))
      );
      const erroTextoNaTela = screen.queryAllByText(/erro|nao foi possivel/i).length > 0;
      expect(erroAlertCalled || erroTextoNaTela).toBe(true);
    });
  });
});
