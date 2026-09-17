import React from 'react';
import { render, fireEvent, waitFor } from '@testing-library/react-native';
import RecordCreateScreen from '../RecordCreateScreen';

jest.mock('../../contexts/AuthContext', () => ({
  useAuth: () => ({ tokens: { access: 'fake-access-token', refresh: 'fake-refresh-token' } }),
}));
import { recordsApi, medicationsApi } from '../../api/endpoints';

// Card #71 — integração do MicrophoneButton no campo de texto livre "O quê"
// (categorias Exercício/Outros): o texto ditado deve ser anexado ao que já
// foi digitado, no mesmo padrão usado no ChatScreen.
//
// Cada asserção de ditado por voz vive num arquivo de teste próprio: uma
// segunda chamada de `render()` na mesma suíte, depois que o botão de
// microfone dispara um `setValue` do react-hook-form, deixa o ambiente de
// teste (react-test-renderer/act) num estado que corrompe o render()
// seguinte — não é uma regressão desta funcionalidade, é uma limitação do
// ambiente de testes já observada aqui; isolar por arquivo evita o problema
// porque o Jest reseta o registro de módulos a cada arquivo.
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
  const { View: RNView, Text: RNText } = require('react-native');
  return function MockDateTimePicker({ label }: { label: string }) {
    return (
      <RNView>
        <RNText>{label}</RNText>
      </RNView>
    );
  };
});

// A tela decide se mostra o MicrophoneButton com base em `isAvailable` do
// hook de voz; mockamos o hook diretamente para manter o teste isolado do
// ciclo assíncrono real de gravação/permissão do reconhecedor nativo.
jest.mock('../../hooks/useSpeechToText', () => ({
  useSpeechToText: () => ({
    status: 'idle',
    error: null,
    isRecording: false,
    isAvailable: true,
    start: jest.fn(),
    stop: jest.fn(),
  }),
}));

// Stub do MicrophoneButton: dispara `onResult` com um texto fixo ao ser
// tocado, sem depender do reconhecedor nativo de voz.
jest.mock('../../components/MicrophoneButton', () => {
  return function MockMicrophoneButton({ onResult, testID }: { onResult: (t: string) => void; testID?: string }) {
    const { TouchableOpacity: RNTouchableOpacity, Text: RNText } = require('react-native');
    return (
      <RNTouchableOpacity testID={testID ?? 'mic-button'} onPress={() => onResult('texto ditado')}>
        <RNText>mic</RNText>
      </RNTouchableOpacity>
    );
  };
});

describe('RecordCreateScreen - ditado por voz no campo "O quê"', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    (medicationsApi.list as jest.Mock).mockResolvedValue({ data: { results: [] } });
  });

  it('anexa o texto ditado ao campo "O quê", preservando o texto já digitado', async () => {
    const { getByText, findByText, getByPlaceholderText, getAllByTestId } = await render(<RecordCreateScreen />);

    await fireEvent.press(getByText('Outros'));
    await findByText('O quê', {}, { timeout: 3000 });

    fireEvent.changeText(getByPlaceholderText('Descreva a atividade'), 'Caminhada');

    // Índice 0: o mic do campo "O quê" aparece antes do de "Observações" na tela.
    await fireEvent.press(getAllByTestId('mic-button')[0]);

    await waitFor(() => {
      expect(getByPlaceholderText('Descreva a atividade').props.value).toBe('Caminhada texto ditado');
    });
    expect(recordsApi.create).not.toHaveBeenCalled();
  }, 15000);
});
