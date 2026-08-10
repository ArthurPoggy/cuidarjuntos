import React from 'react';
import { render, fireEvent, waitFor } from '@testing-library/react-native';
import RecordCreateScreen from '../RecordCreateScreen';
import { recordsApi, medicationsApi } from '../../api/endpoints';

// Tarefa #72: campo "Observações" ganha um botão de ditado por voz
// (MicrophoneButton) que concatena o texto reconhecido ao que já estiver
// digitado. A regra "oculto em Platform.OS === 'web'" combinada com
// "isAvailable" (reconhecedor registrado) é coberta separadamente, como
// função pura, em src/utils/__tests__/voiceInput.test.ts — mockar o módulo
// nativo Platform do react-native para alternar OS durante um render de
// componente se mostrou não confiável neste ambiente (jest-expo resolve
// Platform.ios.js via haste e ignora mocks do caminho não sufixado), então
// aqui validamos o comportamento observável do componente (aparece quando o
// reconhecedor está disponível, concatena texto, some quando indisponível)
// deixando a plataforma como o ambiente de teste padrão do jest-expo (ios).

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

// Simplifica o botão para um TouchableOpacity que, ao ser tocado, dispara
// onResult com um texto fixo — o que importa aqui é o callback recebido de
// RecordCreateScreen, não o funcionamento interno do MicrophoneButton (já
// coberto pelos testes do próprio componente/hook).
jest.mock('../../components/MicrophoneButton', () => {
  const { TouchableOpacity, Text } = require('react-native');
  return function MockMicrophoneButton({ onResult }: { onResult: (text: string) => void }) {
    return (
      <TouchableOpacity testID="mic-button" onPress={() => onResult('texto ditado')}>
        <Text>mic</Text>
      </TouchableOpacity>
    );
  };
});

// isAvailable controlável por teste: útil para exercitar o branch em que o
// botão fica oculto por falta de reconhecedor registrado, sem depender de
// mockar Platform.
let mockVoiceAvailable = true;
jest.mock('../../hooks/useSpeechToText', () => ({
  useSpeechToText: () => ({
    status: 'idle',
    error: null,
    isRecording: false,
    get isAvailable() {
      return mockVoiceAvailable;
    },
    start: jest.fn(),
    stop: jest.fn(),
  }),
}));

async function goToObservacoes(root: Awaited<ReturnType<typeof render>>) {
  const { getByText } = root;
  await fireEvent.press(getByText('Outros'));
}

describe('RecordCreateScreen - ditado por voz em Observações', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockVoiceAvailable = true;
    (medicationsApi.list as jest.Mock).mockResolvedValue({ data: { results: [] } });
  });

  it('exibe o MicrophoneButton ao lado do campo Observações quando o reconhecedor está disponível', async () => {
    const root = await render(<RecordCreateScreen />);
    await goToObservacoes(root);

    expect(root.getByTestId('mic-button')).toBeTruthy();
  }, 15000);

  it('oculta o MicrophoneButton quando não há reconhecedor de voz disponível', async () => {
    mockVoiceAvailable = false;

    const root = await render(<RecordCreateScreen />);
    await goToObservacoes(root);

    expect(root.queryByTestId('mic-button')).toBeNull();
  }, 15000);

  it('concatena o texto reconhecido ao conteúdo já digitado em Observações', async () => {
    const root = await render(<RecordCreateScreen />);
    await goToObservacoes(root);

    const { getByPlaceholderText, getByTestId } = root;
    const descriptionInput = getByPlaceholderText('Detalhes adicionais...');
    fireEvent.changeText(descriptionInput, 'Texto existente');
    await waitFor(() => expect(descriptionInput.props.value).toBe('Texto existente'));

    fireEvent.press(getByTestId('mic-button'));

    await waitFor(() =>
      expect(descriptionInput.props.value).toBe('Texto existente texto ditado')
    );
  }, 15000);

  it('usa apenas o texto ditado quando o campo Observações está vazio', async () => {
    const root = await render(<RecordCreateScreen />);
    await goToObservacoes(root);

    const { getByPlaceholderText, getByTestId } = root;
    const descriptionInput = getByPlaceholderText('Detalhes adicionais...');

    fireEvent.press(getByTestId('mic-button'));

    await waitFor(() => expect(descriptionInput.props.value).toBe('texto ditado'));
  }, 15000);
});
