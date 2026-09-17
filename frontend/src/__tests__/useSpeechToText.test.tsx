import { act, renderHook, waitFor } from '@testing-library/react-native';
import {
  setSpeechRecognizer,
  useSpeechToText,
  type SpeechRecognizer,
  type SpeechRecognizerHandlers,
} from '../hooks/useSpeechToText';

/**
 * Testes automatizados para o card #70 "Testes automatizados de
 * fallback/erro do reconhecimento de voz".
 *
 * A tarefa original do Trello pedia QA manual em iOS/Android/Web (algo que um
 * agente automatizado nao pode executar fisicamente); em vez disso cobrimos
 * aqui, de forma automatizada, os cenarios de fallback/erro do hook:
 * - isAvailable() === false (comportamento tipico da web, onde ainda nao ha
 *   reconhecedor nativo registrado)
 * - permissao de microfone negada
 * - erro lancado ao solicitar permissao
 * - erro emitido pelo reconhecedor durante o start()
 *
 * A verificacao manual em dispositivo real (iOS/Android/Web fisicos)
 * permanece pendente de QA humano - nao e um objetivo automatizavel.
 */
describe('useSpeechToText - fallback e tratamento de erro', () => {
  afterEach(() => {
    // Restaura o stub padrao (indisponivel) para nao vazar mocks entre testes.
    setSpeechRecognizer({
      isAvailable: () => false,
      requestPermission: async () => false,
      start: async () => {
        throw new Error('Reconhecimento de voz não está disponível neste dispositivo.');
      },
      stop: async () => {},
    });
  });

  it('reporta isAvailable=false quando não há reconhecedor de voz registrado (ex.: web)', async () => {
    const { result } = await renderHook(() => useSpeechToText());

    expect(result.current.isAvailable).toBe(false);
  });

  it('vai para status "error" ao chamar start() sem reconhecedor disponível', async () => {
    const onError = jest.fn();
    const { result } = await renderHook(() => useSpeechToText(onError));

    await act(async () => {
      await result.current.start(jest.fn());
    });

    expect(result.current.status).toBe('error');
    expect(result.current.error).toBeInstanceOf(Error);
    expect(onError).toHaveBeenCalledTimes(1);
  });

  it('vai para status "error" quando a permissão de microfone é negada', async () => {
    const recognizer: SpeechRecognizer = {
      isAvailable: () => true,
      requestPermission: async () => false,
      start: jest.fn(),
      stop: jest.fn(),
    };
    setSpeechRecognizer(recognizer);

    const onError = jest.fn();
    const { result } = await renderHook(() => useSpeechToText(onError));

    await act(async () => {
      await result.current.start(jest.fn());
    });

    expect(result.current.status).toBe('error');
    expect(String((result.current.error as Error)?.message)).toMatch(/permiss/i);
    expect(recognizer.start).not.toHaveBeenCalled();
    expect(onError).toHaveBeenCalledTimes(1);
  });

  it('vai para status "error" quando requestPermission() rejeita', async () => {
    const permissionError = new Error('módulo nativo mal configurado');
    const recognizer: SpeechRecognizer = {
      isAvailable: () => true,
      requestPermission: async () => {
        throw permissionError;
      },
      start: jest.fn(),
      stop: jest.fn(),
    };
    setSpeechRecognizer(recognizer);

    const onError = jest.fn();
    const { result } = await renderHook(() => useSpeechToText(onError));

    await act(async () => {
      await result.current.start(jest.fn());
    });

    expect(result.current.status).toBe('error');
    expect(result.current.error).toBe(permissionError);
    expect(onError).toHaveBeenCalledWith(permissionError);
  });

  it('vai para status "error" quando o reconhecedor emite onError durante a gravação', async () => {
    let handlers: SpeechRecognizerHandlers | null = null;
    const recognitionError = new Error('falha ao capturar áudio');
    const recognizer: SpeechRecognizer = {
      isAvailable: () => true,
      requestPermission: async () => true,
      start: async (h) => {
        handlers = h;
      },
      stop: jest.fn(),
    };
    setSpeechRecognizer(recognizer);

    const onError = jest.fn();
    const { result } = await renderHook(() => useSpeechToText(onError));

    await act(async () => {
      await result.current.start(jest.fn());
    });

    expect(result.current.status).toBe('recording');

    await act(async () => {
      handlers?.onError(recognitionError);
    });

    expect(result.current.status).toBe('error');
    expect(result.current.error).toBe(recognitionError);
    expect(onError).toHaveBeenCalledWith(recognitionError);
  });

  it('start() lançada com erro não chama o callback onResult', async () => {
    const recognizer: SpeechRecognizer = {
      isAvailable: () => true,
      requestPermission: async () => true,
      start: async () => {
        throw new Error('start indisponível');
      },
      stop: jest.fn(),
    };
    setSpeechRecognizer(recognizer);

    const onResult = jest.fn();
    const { result } = await renderHook(() => useSpeechToText());

    await act(async () => {
      await result.current.start(onResult);
    });

    expect(result.current.status).toBe('error');
    expect(onResult).not.toHaveBeenCalled();
  });
});
