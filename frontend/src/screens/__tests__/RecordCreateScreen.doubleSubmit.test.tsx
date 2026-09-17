import React from 'react';
import { render, fireEvent, waitFor } from '@testing-library/react-native';
import RecordCreateScreen from '../RecordCreateScreen';

jest.mock('../../contexts/AuthContext', () => ({
  useAuth: () => ({ tokens: { access: 'fake-access-token', refresh: 'fake-refresh-token' } }),
}));
import { recordsApi, medicationsApi } from '../../api/endpoints';

// Avoid touching axios/SecureStore and native navigation wiring — this test
// exercises the double-tap guard around record submission in isolation, so
// that its slow-resolving mock request cannot leak into other test files.
jest.mock('../../api/endpoints', () => ({
  // O RecordCreateScreen consulta o status das integracoes de
  // calendario ao montar (card #41); sem este mock o modulo real
  // seria importado e a chamada iria para o axios.
  integrationsApi: {
    calendarStatus: jest.fn(() =>
      Promise.resolve({ data: { connected: false, providers: [] } })
    ),
  },
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

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((res) => {
    resolve = res;
  });
  return { promise, resolve };
}

describe('RecordCreateScreen - evita envio duplicado', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('desabilita o botão e evita envios duplicados durante o processamento', async () => {
    const { promise, resolve } = deferred<{ data: unknown }>();
    (recordsApi.create as jest.Mock).mockReturnValue(promise);

    const { getByText, findByText } = await render(<RecordCreateScreen />);

    await fireEvent.press(getByText('Exercício'));

    const whatInput = await findByText('O quê');
    expect(whatInput).toBeTruthy();

    const submitButton = await findByText('Salvar');

    // Double/triple-tap rapidly before the request resolves.
    fireEvent.press(submitButton);
    fireEvent.press(submitButton);
    fireEvent.press(submitButton);

    await waitFor(() => expect(recordsApi.create).toHaveBeenCalled());
    expect(recordsApi.create).toHaveBeenCalledTimes(1);

    resolve({ data: {} });
    await waitFor(() => expect(mockGoBack).toHaveBeenCalled());
  }, 40000);
});
