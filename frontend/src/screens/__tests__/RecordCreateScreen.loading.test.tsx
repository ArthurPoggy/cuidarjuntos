import React from 'react';
import { Alert } from 'react-native';
import { render, fireEvent, waitFor } from '@testing-library/react-native';
import RecordCreateScreen from '../RecordCreateScreen';

jest.mock('../../contexts/AuthContext', () => ({
  useAuth: () => ({ tokens: { access: 'fake-access-token', refresh: 'fake-refresh-token' } }),
}));
import { recordsApi, medicationsApi } from '../../api/endpoints';

// Avoid touching axios/SecureStore and native navigation wiring — this test
// exercises the success/error feedback around record submission.
jest.mock('../../api/endpoints', () => ({
  recordsApi: {
    create: jest.fn(),
    update: jest.fn(),
  },
  medicationsApi: {
    list: jest.fn(() => Promise.resolve({ data: { results: [] } })),
  },
}));

jest.mock('@react-native-async-storage/async-storage', () => ({
  getItem: jest.fn(() => Promise.resolve(null)),
  setItem: jest.fn(() => Promise.resolve()),
  removeItem: jest.fn(() => Promise.resolve()),
}));

const mockGoBack = jest.fn();
jest.mock('@react-navigation/native', () => ({
  useNavigation: () => ({ goBack: mockGoBack }),
  useRoute: () => ({ params: {} }),
}));

jest.mock('../../components/DateTimePicker', () => {
  const { View, Text } = require('react-native');
  return function MockDateTimePicker({ label }: { label: string }) {
    return (
      <View>
        <Text>{label}</Text>
      </View>
    );
  };
});

describe('RecordCreateScreen - feedback de envio', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    jest.spyOn(Alert, 'alert').mockImplementation(() => undefined);
  });

  afterEach(() => {
    (Alert.alert as jest.Mock).mockRestore();
  });

  it('exibe feedback de sucesso claro após salvar o registro', async () => {
    (recordsApi.create as jest.Mock).mockResolvedValue({ data: {} });

    const { getByText, findByText } = await render(<RecordCreateScreen />);

    await fireEvent.press(getByText('Exercício'));
    const submitButton = await findByText('Salvar');
    await fireEvent.press(submitButton);

    await waitFor(() => {
      expect(Alert.alert).toHaveBeenCalledWith(
        expect.stringMatching(/sucesso/i),
        expect.any(String),
      );
    });
    await waitFor(() => expect(mockGoBack).toHaveBeenCalled());
  });

  it('exibe feedback de erro claro e reabilita o botão quando o envio falha', async () => {
    (recordsApi.create as jest.Mock).mockRejectedValue({
      response: { data: 'Falha ao salvar' },
    });

    const { getByText, findByText } = await render(<RecordCreateScreen />);

    await fireEvent.press(getByText('Exercício'));
    const submitButton = await findByText('Salvar');
    await fireEvent.press(submitButton);

    await waitFor(() => {
      expect(Alert.alert).toHaveBeenCalledWith('Erro', expect.any(String));
    });
    expect(mockGoBack).not.toHaveBeenCalled();

    // Button should be usable again after the failed attempt.
    (recordsApi.create as jest.Mock).mockResolvedValue({ data: {} });
    await fireEvent.press(submitButton);
    await waitFor(() => expect(recordsApi.create).toHaveBeenCalledTimes(2));
  });
});
