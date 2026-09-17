import React from 'react';
import { render, fireEvent, waitFor } from '@testing-library/react-native';
import RecordCreateScreen from '../RecordCreateScreen';

jest.mock('../../contexts/AuthContext', () => ({
  useAuth: () => ({ tokens: { access: 'fake-access-token', refresh: 'fake-refresh-token' } }),
}));
import { recordsApi, medicationsApi } from '../../api/endpoints';

// Card #71 — integração do MicrophoneButton no campo de texto livre
// "Observações" (comum a todas as categorias de registro): o texto ditado
// deve ser anexado ao que já foi digitado. Ver RecordCreateScreen.voiceWhat
// para o motivo do teste viver isolado num arquivo próprio.
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

describe('RecordCreateScreen - ditado por voz no campo "Observações"', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    (medicationsApi.list as jest.Mock).mockResolvedValue({ data: { results: [] } });
  });

  it('anexa o texto ditado ao campo "Observações", preservando o texto já digitado', async () => {
    const { getByText, findByText, getByPlaceholderText, getAllByTestId } = await render(<RecordCreateScreen />);

    await fireEvent.press(getByText('Outros'));
    await findByText('O quê', {}, { timeout: 3000 });

    fireEvent.changeText(getByPlaceholderText('Detalhes adicionais...'), 'Paciente estava bem');

    const micButtons = getAllByTestId('mic-button');
    // Índice 1: o mic do campo "Observações" aparece depois do de "O quê".
    await fireEvent.press(micButtons[1]);

    await waitFor(() => {
      expect(getByPlaceholderText('Detalhes adicionais...').props.value).toBe('Paciente estava bem texto ditado');
    });
    expect(recordsApi.create).not.toHaveBeenCalled();
  }, 15000);
});
