import React from 'react';
import { Alert } from 'react-native';
import { render, screen, waitFor, fireEvent } from '@testing-library/react-native';

jest.setTimeout(20000);

jest.mock('react-native-safe-area-context', () =>
  require('react-native-safe-area-context/jest/mock').default
);

const mockGoBack = jest.fn();
jest.mock('@react-navigation/native', () => ({
  useNavigation: () => ({ goBack: mockGoBack, navigate: jest.fn() }),
  useRoute: () => ({ params: { id: 1 } }),
}));

jest.mock('../../api/endpoints', () => ({
  recordsApi: {
    get: jest.fn(),
    getComments: jest.fn(),
    delete: jest.fn(),
    react: jest.fn(),
    addComment: jest.fn(),
  },
}));

import { recordsApi } from '../../api/endpoints';
import RecordDetailScreen from '../RecordDetailScreen';

const mockedGet = recordsApi.get as jest.Mock;
const mockedGetComments = recordsApi.getComments as jest.Mock;
const mockedDelete = recordsApi.delete as jest.Mock;

const buildRecord = () => ({
  id: 1,
  type: 'medication',
  what: 'Paracetamol',
  status: 'pending',
  date: '2026-08-08',
  time: '08:00:00',
  author_name: 'Maria',
  caregiver: 'Maria',
  description: '',
  medication_detail: '',
  capsule_quantity: null,
  progress_trend: '',
  recurrence: 'none',
  is_exception: false,
  social: { counts: {}, user_reaction: '', comments_count: 0 },
});

describe('RecordDetailScreen', () => {
  beforeEach(() => {
    mockedGet.mockReset();
    mockedGetComments.mockReset();
    mockedDelete.mockReset();
    mockGoBack.mockReset();
    jest.spyOn(Alert, 'alert').mockImplementation(() => {});
  });

  afterEach(() => {
    (Alert.alert as jest.Mock).mockRestore();
  });

  describe('excluir registro', () => {
    it('nao chama Alert.alert e exibe o ConfirmModal ao tocar em excluir', async () => {
      mockedGet.mockResolvedValueOnce({ data: buildRecord() });
      mockedGetComments.mockResolvedValueOnce({ data: [] });

      render(<RecordDetailScreen />);

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
      mockedGet.mockResolvedValueOnce({ data: buildRecord() });
      mockedGetComments.mockResolvedValueOnce({ data: [] });

      render(<RecordDetailScreen />);

      await waitFor(() => {
        expect(screen.getByText('Excluir')).toBeTruthy();
      });

      fireEvent.press(screen.getByText('Excluir'));

      await waitFor(() => {
        expect(
          screen.getByText('Tem certeza que deseja excluir este registro?')
        ).toBeTruthy();
      });

      fireEvent.press(screen.getByText('Cancelar'));

      expect(mockedDelete).not.toHaveBeenCalled();
      await waitFor(() => {
        expect(
          screen.queryByText('Tem certeza que deseja excluir este registro?')
        ).toBeNull();
      });
    });

    it('ao confirmar no ConfirmModal, chama recordsApi.delete com o id correto e volta a tela anterior', async () => {
      mockedGet.mockResolvedValueOnce({ data: buildRecord() });
      mockedGetComments.mockResolvedValueOnce({ data: [] });
      mockedDelete.mockResolvedValueOnce({ data: {} });

      render(<RecordDetailScreen />);

      await waitFor(() => {
        expect(screen.getByText('Excluir')).toBeTruthy();
      });

      fireEvent.press(screen.getByText('Excluir'));

      await waitFor(() => {
        expect(
          screen.getByText('Tem certeza que deseja excluir este registro?')
        ).toBeTruthy();
      });

      fireEvent.press(screen.getByTestId('confirm-modal-confirm-button'));

      await waitFor(() => {
        expect(mockedDelete).toHaveBeenCalledWith(1);
      });
      await waitFor(() => {
        expect(mockGoBack).toHaveBeenCalledTimes(1);
      });
    });

    it('exibe Alert.alert de erro quando a exclusao falha, sem regressao', async () => {
      mockedGet.mockResolvedValueOnce({ data: buildRecord() });
      mockedGetComments.mockResolvedValueOnce({ data: [] });
      mockedDelete.mockRejectedValueOnce(new Error('network error'));

      render(<RecordDetailScreen />);

      await waitFor(() => {
        expect(screen.getByText('Excluir')).toBeTruthy();
      });

      fireEvent.press(screen.getByText('Excluir'));

      await waitFor(() => {
        expect(
          screen.getByText('Tem certeza que deseja excluir este registro?')
        ).toBeTruthy();
      });

      fireEvent.press(screen.getByTestId('confirm-modal-confirm-button'));

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
