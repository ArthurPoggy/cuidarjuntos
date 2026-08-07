import React from 'react';
import { render, fireEvent, waitFor } from '@testing-library/react-native';
import RecordCreateScreen from '../RecordCreateScreen';
import { recordsApi, medicationsApi } from '../../api/endpoints';

// Avoid touching axios/SecureStore and native navigation wiring — this test
// exercises the MEDICATION branch of renderTypeSpecificFields in isolation.
jest.mock('../../api/endpoints', () => ({
  recordsApi: {
    create: jest.fn(() => Promise.resolve({ data: {} })),
    update: jest.fn(() => Promise.resolve({ data: {} })),
  },
  medicationsApi: {
    list: jest.fn(() => Promise.resolve({ data: { results: [] } })),
  },
}));

// utils/constants imports AsyncStorage at module scope for API_BASE_URL
// resolution; the native module isn't available under jest-expo, so stub it.
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

// The native date/time picker widget is irrelevant to the medication flow
// under test; stub it out so it doesn't pull in native module internals.
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

describe('RecordCreateScreen - fluxo Adicionar remédio', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    (medicationsApi.list as jest.Mock).mockResolvedValue({ data: { results: [] } });
  });

  it('exibe erro inline e não envia para a API ao submeter "Outro" sem preencher o medicamento', async () => {
    const { getByText, findByText, queryByText } = await render(<RecordCreateScreen />);

    // Step 1: escolhe a categoria "Remédio" (RecordType.MEDICATION)
    await fireEvent.press(getByText('Remédio'));

    // Step 2: aguarda o carregamento dos medicamentos e seleciona "Outro"
    const otherOption = await findByText('Outro', {}, { timeout: 3000 });
    await fireEvent.press(otherOption);

    // Não preenche "Outro medicamento/dose" e tenta submeter
    const submitButton = await findByText('Salvar', {}, { timeout: 3000 });
    await fireEvent.press(submitButton);

    // Deve exibir uma mensagem de erro inline (via formState.errors / FormField),
    // sem depender de Alert.alert.
    await waitFor(
      () => {
        expect(queryByText(/informe o nome do medicamento/i)).toBeTruthy();
      },
      { timeout: 3000 }
    );

    // O submit não deve ter chamado a API.
    expect(recordsApi.create).not.toHaveBeenCalled();
  }, 15000);
});
