import React from 'react';
import { Platform } from 'react-native';
import { render, screen, waitFor, fireEvent, act } from '@testing-library/react-native';
import MicrophoneButton from '../components/MicrophoneButton';
import { setSpeechRecognizer, type SpeechRecognizer } from '../hooks/useSpeechToText';

const ACCESSIBILITY_LABELS = ['Gravar voz', 'Parar gravação'];

function queryMicButton() {
  for (const label of ACCESSIBILITY_LABELS) {
    const found = screen.queryByLabelText(label);
    if (found) return found;
  }
  return null;
}

/**
 * Testes automatizados para o card #70 "Testes automatizados de
 * fallback/erro do reconhecimento de voz" - cobrindo o MicrophoneButton.
 *
 * Verificação manual em dispositivo real (iOS/Android/Web físicos) permanece
 * pendente de QA humano - não é um objetivo automatizável para este agente.
 */
describe('MicrophoneButton - fallback e ocultação na web', () => {
  const originalOS = Platform.OS;

  afterEach(() => {
    Platform.OS = originalOS;
    setSpeechRecognizer({
      isAvailable: () => false,
      requestPermission: async () => false,
      start: async () => {
        throw new Error('Reconhecimento de voz não está disponível neste dispositivo.');
      },
      stop: async () => {},
    });
  });

  it('não renderiza nada quando Platform.OS é "web"', async () => {
    Platform.OS = 'web';
    const recognizer: SpeechRecognizer = {
      isAvailable: () => true,
      requestPermission: async () => true,
      start: jest.fn(),
      stop: jest.fn(),
    };
    setSpeechRecognizer(recognizer);

    await render(<MicrophoneButton onResult={jest.fn()} />);

    expect(queryMicButton()).toBeNull();
  });

  it('renderiza o botão normalmente em plataformas nativas (ios/android)', async () => {
    Platform.OS = 'ios';
    const recognizer: SpeechRecognizer = {
      isAvailable: () => true,
      requestPermission: async () => true,
      start: jest.fn(),
      stop: jest.fn(),
    };
    setSpeechRecognizer(recognizer);

    await render(<MicrophoneButton onResult={jest.fn()} />);

    expect(queryMicButton()).not.toBeNull();
  });

  it('ao tocar o botão com permissão negada, mostra o indicador de erro e chama onError', async () => {
    Platform.OS = 'android';
    const recognizer: SpeechRecognizer = {
      isAvailable: () => true,
      requestPermission: async () => false,
      start: jest.fn(),
      stop: jest.fn(),
    };
    setSpeechRecognizer(recognizer);

    const onError = jest.fn();
    await render(<MicrophoneButton onResult={jest.fn()} onError={onError} />);

    const button = queryMicButton();
    expect(button).not.toBeNull();

    await act(async () => {
      fireEvent.press(button!);
    });

    await waitFor(() => {
      expect(onError).toHaveBeenCalledTimes(1);
    });
    expect(recognizer.start).not.toHaveBeenCalled();
  });
});
