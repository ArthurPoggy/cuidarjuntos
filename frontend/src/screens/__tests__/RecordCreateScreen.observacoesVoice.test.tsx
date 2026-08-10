import React from 'react';
import { Platform } from 'react-native';
import { render, fireEvent, waitFor, act } from '@testing-library/react-native';
import RecordCreateScreen from '../RecordCreateScreen';
import { recordsApi, medicationsApi } from '../../api/endpoints';

// Card #72: MicrophoneButton integrado ao campo "Observações" da tela de
// criação de registro. Cobre os três critérios de aceitação: (1) o botão
// aparece ao lado do TextInput de observações, (2) fica oculto quando
// Platform.OS === 'web', (3) o texto reconhecido é concatenado ao texto já
// digitado em vez de substituí-lo.

jest.mock('../../api/endpoints', () => ({
  recordsApi: {
    create: jest.fn(() => Promise.resolve({ data: {} })),
    update: jest.fn(() => Promise.resolve({ data: {} })),
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

// Substitui o MicrophoneButton real por um stub que expõe seu `onResult`
// através de um TouchableOpacity clicável, evitando depender do hook nativo
// de reconhecimento de voz (que não está disponível em ambiente de teste).
let capturedOnResult: ((text: string) => void) | null = null;
jest.mock('../../components/MicrophoneButton', () => {
  const { TouchableOpacity, Text } = require('react-native');
  return function MockMicrophoneButton({ onResult }: { onResult: (text: string) => void }) {
    capturedOnResult = onResult;
    return (
      <TouchableOpacity onPress={() => onResult('texto ditado')} accessibilityLabel="Gravar voz">
        <Text>mic-stub</Text>
      </TouchableOpacity>
    );
  };
});

async function goToStep2(getByText: any, findByText: any) {
  await fireEvent.press(getByText('Outros'));
  await findByText('O quê', {}, { timeout: 3000 });
}

describe('RecordCreateScreen - ditado por voz no campo Observações', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    capturedOnResult = null;
    (medicationsApi.list as jest.Mock).mockResolvedValue({ data: { results: [] } });

    Platform.OS = 'ios';
  });

  it('exibe o botão de microfone ao lado do campo Observações em plataformas nativas', async () => {
    const { getByText, findByText, getByPlaceholderText, getByLabelText } = await render(
      <RecordCreateScreen />
    );

    await goToStep2(getByText, findByText);

    expect(getByPlaceholderText('Detalhes adicionais...')).toBeTruthy();
    expect(getByLabelText('Gravar voz')).toBeTruthy();
  }, 15000);

  it('oculta o botão de microfone quando Platform.OS === "web"', async () => {
    Platform.OS = 'web';

    const { getByText, findByText, getByPlaceholderText, queryByLabelText } = await render(
      <RecordCreateScreen />
    );

    await goToStep2(getByText, findByText);

    expect(getByPlaceholderText('Detalhes adicionais...')).toBeTruthy();
    expect(queryByLabelText('Gravar voz')).toBeNull();
  }, 15000);

  it('concatena o texto reconhecido ao texto já digitado em Observações', async () => {
    const { getByText, findByText, getByPlaceholderText } = await render(<RecordCreateScreen />);

    await goToStep2(getByText, findByText);

    const input = getByPlaceholderText('Detalhes adicionais...');
    fireEvent.changeText(input, 'Já escrevi isso.');

    await waitFor(() => {
      expect(getByPlaceholderText('Detalhes adicionais...').props.value).toBe('Já escrevi isso.');
    });

    expect(capturedOnResult).not.toBeNull();
    await act(async () => {
      capturedOnResult!('mais um trecho ditado');
    });

    await waitFor(() => {
      expect(getByPlaceholderText('Detalhes adicionais...').props.value).toBe(
        'Já escrevi isso. mais um trecho ditado'
      );
    });
  }, 15000);
});
