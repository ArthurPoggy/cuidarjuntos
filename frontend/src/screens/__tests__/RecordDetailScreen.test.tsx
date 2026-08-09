import React from 'react';
import { Alert } from 'react-native';
import { render, screen, waitFor, fireEvent } from '@testing-library/react-native';
import { RecordType, RecordStatus, Recurrence } from '../../types/models';
import type { CareRecord } from '../../types/models';

/**
 * Tarefa #88 "Integrar exclusao de registros no app" (subtasks 2 e 3) +
 * tarefa #89 "Modal de confirmacao para acoes destrutivas": cobre a
 * visibilidade do botao "Excluir" conforme a regra de permissao
 * (record.created_by === user.id OU user.profile.role === 'ADMIN') e o
 * fluxo de confirmacao via ConfirmModal (nao mais Alert.alert nativo).
 */

jest.setTimeout(20000);

jest.mock('react-native-safe-area-context', () =>
  require('react-native-safe-area-context/jest/mock').default
);

jest.mock('../../api/endpoints', () => ({
  recordsApi: {
    get: jest.fn(),
    getComments: jest.fn(),
    react: jest.fn(),
    addComment: jest.fn(),
    delete: jest.fn(),
  },
}));

const mockGoBack = jest.fn();
jest.mock('@react-navigation/native', () => ({
  useNavigation: () => ({ goBack: mockGoBack, navigate: jest.fn() }),
  useRoute: () => ({ params: { id: 1 } }),
}));

let mockUser: { id: number; profile: { role: string } } | null = null;
jest.mock('../../contexts/AuthContext', () => ({
  useAuth: () => ({ user: mockUser }),
}));

import { recordsApi } from '../../api/endpoints';
import RecordDetailScreen from '../RecordDetailScreen';

const mockedGet = recordsApi.get as jest.Mock;
const mockedGetComments = recordsApi.getComments as jest.Mock;
const mockedDelete = recordsApi.delete as jest.Mock;

function buildRecord(overrides: Partial<CareRecord> = {}): CareRecord {
  return {
    id: 1,
    patient: 1,
    type: RecordType.MEDICATION,
    what: 'Dipirona',
    description: '',
    medication: null,
    capsule_quantity: null,
    progress_trend: '',
    missed_reason: '',
    is_exception: false,
    date: '2026-08-08',
    time: '08:00:00',
    recurrence: Recurrence.NONE,
    repeat_until: null,
    status: RecordStatus.DONE,
    caregiver: 'Fulano',
    created_by: 10,
    timestamp: '2026-08-08T08:00:00Z',
    recurrence_group: null,
    author_name: 'Fulano',
    medication_detail: '',
    is_from_series: false,
    social: { counts: {}, user_reaction: '', comments_count: 0 },
    ...overrides,
  } as CareRecord;
}

describe('RecordDetailScreen - exclusao de registro', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockedGetComments.mockResolvedValue({ data: [] });
    jest.spyOn(Alert, 'alert').mockImplementation(() => {});
  });

  afterEach(() => {
    (Alert.alert as jest.Mock).mockRestore();
  });

  describe('visibilidade do botao Excluir (permissao)', () => {
    it('nao renderiza o botao Excluir para usuario que nao e dono nem ADMIN', async () => {
      mockedGet.mockResolvedValueOnce({ data: buildRecord({ created_by: 10 }) });
      mockUser = { id: 99, profile: { role: 'CAREGIVER' } };

      await render(<RecordDetailScreen />);

      await waitFor(() => {
        expect(screen.getByText('Dipirona')).toBeTruthy();
      });

      expect(screen.queryByText('Excluir')).toBeNull();
    });

    it('renderiza o botao Excluir para o dono do registro', async () => {
      mockedGet.mockResolvedValueOnce({ data: buildRecord({ created_by: 42 }) });
      mockUser = { id: 42, profile: { role: 'CAREGIVER' } };

      await render(<RecordDetailScreen />);

      await waitFor(() => {
        expect(screen.getByText('Dipirona')).toBeTruthy();
      });

      expect(screen.getByText('Excluir')).toBeTruthy();
    });

    it('renderiza o botao Excluir para usuario com profile.role ADMIN mesmo sem ser dono', async () => {
      mockedGet.mockResolvedValueOnce({ data: buildRecord({ created_by: 10 }) });
      mockUser = { id: 99, profile: { role: 'ADMIN' } };

      await render(<RecordDetailScreen />);

      await waitFor(() => {
        expect(screen.getByText('Dipirona')).toBeTruthy();
      });

      expect(screen.getByText('Excluir')).toBeTruthy();
    });
  });

  describe('fluxo de confirmacao via ConfirmModal', () => {
    beforeEach(() => {
      mockUser = { id: 42, profile: { role: 'CAREGIVER' } };
    });

    it('nao chama Alert.alert e exibe o ConfirmModal ao tocar em excluir', async () => {
      mockedGet.mockResolvedValueOnce({ data: buildRecord({ created_by: 42 }) });

      await render(<RecordDetailScreen />);

      await waitFor(() => {
        expect(screen.getByText('Excluir')).toBeTruthy();
      });

      await fireEvent.press(screen.getByText('Excluir'));

      expect(Alert.alert).not.toHaveBeenCalled();
      expect(
        screen.getByText('Tem certeza que deseja excluir este registro?')
      ).toBeTruthy();
    });

    it('ao cancelar no ConfirmModal, nao chama a API de delete', async () => {
      mockedGet.mockResolvedValueOnce({ data: buildRecord({ created_by: 42 }) });

      await render(<RecordDetailScreen />);

      await waitFor(() => {
        expect(screen.getByText('Excluir')).toBeTruthy();
      });

      await fireEvent.press(screen.getByText('Excluir'));

      await waitFor(() => {
        expect(
          screen.getByText('Tem certeza que deseja excluir este registro?')
        ).toBeTruthy();
      });

      await fireEvent.press(screen.getByText('Cancelar'));

      expect(mockedDelete).not.toHaveBeenCalled();
      await waitFor(() => {
        expect(
          screen.queryByText('Tem certeza que deseja excluir este registro?')
        ).toBeNull();
      });
    });

    it('ao confirmar no ConfirmModal, chama recordsApi.delete com o id correto e volta a tela anterior', async () => {
      mockedGet.mockResolvedValueOnce({ data: buildRecord({ created_by: 42 }) });
      mockedDelete.mockResolvedValueOnce({ data: {} });

      await render(<RecordDetailScreen />);

      await waitFor(() => {
        expect(screen.getByText('Excluir')).toBeTruthy();
      });

      await fireEvent.press(screen.getByText('Excluir'));

      await waitFor(() => {
        expect(
          screen.getByText('Tem certeza que deseja excluir este registro?')
        ).toBeTruthy();
      });

      await fireEvent.press(screen.getByTestId('confirm-modal-confirm-button'));

      await waitFor(() => {
        expect(mockedDelete).toHaveBeenCalledWith(1);
      });
      await waitFor(() => {
        expect(mockGoBack).toHaveBeenCalledTimes(1);
      });
    });

    it('exibe Alert.alert de erro quando a exclusao falha, sem regressao', async () => {
      mockedGet.mockResolvedValueOnce({ data: buildRecord({ created_by: 42 }) });
      mockedDelete.mockRejectedValueOnce(new Error('network error'));

      await render(<RecordDetailScreen />);

      await waitFor(() => {
        expect(screen.getByText('Excluir')).toBeTruthy();
      });

      await fireEvent.press(screen.getByText('Excluir'));

      await waitFor(() => {
        expect(
          screen.getByText('Tem certeza que deseja excluir este registro?')
        ).toBeTruthy();
      });

      await fireEvent.press(screen.getByTestId('confirm-modal-confirm-button'));

      await waitFor(() => {
        expect(Alert.alert).toHaveBeenCalledWith(
          'Erro',
          'Nao foi possivel excluir o registro.'
        );
      });
      expect(mockGoBack).not.toHaveBeenCalled();
    });
  });
});
