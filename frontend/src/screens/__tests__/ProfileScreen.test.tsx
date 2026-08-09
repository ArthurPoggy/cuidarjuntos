import React from 'react';
import { Alert } from 'react-native';
import { render, screen, waitFor, fireEvent } from '@testing-library/react-native';

jest.setTimeout(20000);

jest.mock('react-native-safe-area-context', () =>
  require('react-native-safe-area-context/jest/mock').default
);

jest.mock('@react-navigation/native', () => ({
  useNavigation: () => ({ navigate: jest.fn() }),
}));

jest.mock('../../api/endpoints', () => ({
  groupsApi: {
    leave: jest.fn(),
  },
}));

const mockRefreshGroup = jest.fn();
const mockLogout = jest.fn();
const mockUseAuth = jest.fn();
jest.mock('../../contexts/AuthContext', () => ({
  useAuth: () => mockUseAuth(),
}));

import { groupsApi } from '../../api/endpoints';
import ProfileScreen from '../ProfileScreen';

const mockedLeave = groupsApi.leave as jest.Mock;

const buildAuthState = () => ({
  user: {
    username: 'maria',
    email: 'maria@example.com',
    profile: { full_name: 'Maria Silva' },
    membership: { relation_to_patient: 'Filha' },
  },
  group: {
    name: 'Familia Silva',
    patient: { name: 'Jose Silva' },
    member_count: 3,
  },
  logout: mockLogout,
  refreshGroup: mockRefreshGroup,
});

describe('ProfileScreen', () => {
  beforeEach(() => {
    mockedLeave.mockReset();
    mockRefreshGroup.mockReset();
    mockLogout.mockReset();
    mockUseAuth.mockReset();
    mockUseAuth.mockReturnValue(buildAuthState());
    jest.spyOn(Alert, 'alert').mockImplementation(() => {});
  });

  afterEach(() => {
    (Alert.alert as jest.Mock).mockRestore();
  });

  describe('sair do grupo', () => {
    it('nao chama Alert.alert e exibe o ConfirmModal ao tocar em "Sair do Grupo"', async () => {
      await render(<ProfileScreen />);

      await waitFor(() => {
        expect(screen.getByText('Sair do Grupo')).toBeTruthy();
      });

      await fireEvent.press(screen.getByText('Sair do Grupo'));

      expect(Alert.alert).not.toHaveBeenCalled();
      expect(
        screen.getByText('Tem certeza que deseja sair do grupo? Voce perdera acesso aos registros.')
      ).toBeTruthy();
    });

    it('ao cancelar no ConfirmModal, nenhuma chamada de groupsApi.leave e feita', async () => {
      await render(<ProfileScreen />);

      await waitFor(() => {
        expect(screen.getByText('Sair do Grupo')).toBeTruthy();
      });

      await fireEvent.press(screen.getByText('Sair do Grupo'));

      await waitFor(() => {
        expect(
          screen.getByText('Tem certeza que deseja sair do grupo? Voce perdera acesso aos registros.')
        ).toBeTruthy();
      });

      await fireEvent.press(screen.getByText('Cancelar'));

      expect(mockedLeave).not.toHaveBeenCalled();
      await waitFor(() => {
        expect(
          screen.queryByText('Tem certeza que deseja sair do grupo? Voce perdera acesso aos registros.')
        ).toBeNull();
      });
    });

    it('chama groupsApi.leave e refreshGroup ao confirmar no ConfirmModal', async () => {
      mockedLeave.mockResolvedValueOnce({ data: {} });

      await render(<ProfileScreen />);

      await waitFor(() => {
        expect(screen.getByText('Sair do Grupo')).toBeTruthy();
      });

      await fireEvent.press(screen.getByText('Sair do Grupo'));

      await waitFor(() => {
        expect(
          screen.getByText('Tem certeza que deseja sair do grupo? Voce perdera acesso aos registros.')
        ).toBeTruthy();
      });

      await fireEvent.press(screen.getByTestId('confirm-modal-confirm-button'));

      await waitFor(() => {
        expect(mockedLeave).toHaveBeenCalledTimes(1);
      });
      await waitFor(() => {
        expect(mockRefreshGroup).toHaveBeenCalledTimes(1);
      });
    });

    it('exibe Alert.alert de erro quando sair do grupo falha', async () => {
      mockedLeave.mockRejectedValueOnce(new Error('network error'));

      await render(<ProfileScreen />);

      await waitFor(() => {
        expect(screen.getByText('Sair do Grupo')).toBeTruthy();
      });

      await fireEvent.press(screen.getByText('Sair do Grupo'));

      await waitFor(() => {
        expect(
          screen.getByText('Tem certeza que deseja sair do grupo? Voce perdera acesso aos registros.')
        ).toBeTruthy();
      });

      await fireEvent.press(screen.getByTestId('confirm-modal-confirm-button'));

      await waitFor(() => {
        expect(Alert.alert).toHaveBeenCalledWith('Erro', 'Nao foi possivel sair do grupo.');
      });
      expect(mockRefreshGroup).not.toHaveBeenCalled();
    });
  });

  it('nao exibe a secao de grupo com botao "Sair do Grupo" quando o usuario nao esta em nenhum grupo', async () => {
    mockUseAuth.mockReturnValue({ ...buildAuthState(), group: null });

    await render(<ProfileScreen />);

    await waitFor(() => {
      expect(screen.getByText('Voce nao esta em nenhum grupo.')).toBeTruthy();
    });

    expect(screen.queryByText('Sair do Grupo')).toBeNull();
  });
});
