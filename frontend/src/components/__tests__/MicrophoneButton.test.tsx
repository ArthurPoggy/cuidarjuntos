import React from 'react';
import { Platform } from 'react-native';
import { render } from '@testing-library/react-native';

/**
 * Testes automatizados para o card #70 ("Testes automatizados de
 * fallback/erro do reconhecimento de voz"). A tarefa original do Trello
 * pedia QA manual em iOS/Android/Web, algo que este agente não pode
 * executar fisicamente -- cobrimos aqui, de forma automatizada:
 *
 *   - O botão fica oculto quando `Platform.OS === 'web'` (o reconhecimento
 *     de voz nativo ainda não está disponível na versão web do app).
 *   - O botão continua visível em plataformas nativas (iOS/Android).
 *
 * A verificação manual em dispositivo real continua pendente de QA humano
 * -- não é um objetivo automatizável.
 */

const mockUseSpeechToText = jest.fn();

jest.mock('../../hooks/useSpeechToText', () => ({
  useSpeechToText: (...args: unknown[]) => mockUseSpeechToText(...args),
}));

import MicrophoneButton from '../MicrophoneButton';

describe('MicrophoneButton', () => {
  const originalOS = Platform.OS;

  beforeEach(() => {
    mockUseSpeechToText.mockReturnValue({
      status: 'idle',
      isRecording: false,
      start: jest.fn(),
      stop: jest.fn(),
    });
  });

  afterEach(() => {
    Platform.OS = originalOS;
  });

  it('não renderiza nada quando Platform.OS é "web"', async () => {
    Platform.OS = 'web';

    const { queryByLabelText, toJSON } = await render(
      <MicrophoneButton onResult={() => {}} />
    );

    expect(queryByLabelText('Gravar voz')).toBeNull();
    expect(toJSON()).toBeNull();
  });

  it('renderiza o botão normalmente em plataformas nativas (ex.: ios)', async () => {
    Platform.OS = 'ios';

    const { getByLabelText } = await render(<MicrophoneButton onResult={() => {}} />);

    expect(getByLabelText('Gravar voz')).toBeTruthy();
  });

  it('renderiza o botão normalmente no android', async () => {
    Platform.OS = 'android';

    const { getByLabelText } = await render(<MicrophoneButton onResult={() => {}} />);

    expect(getByLabelText('Gravar voz')).toBeTruthy();
  });
});
