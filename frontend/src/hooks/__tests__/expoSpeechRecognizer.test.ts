/**
 * Testes para o item do card #77 "Adicionar biblioteca de reconhecimento de
 * voz": registrar um `SpeechRecognizer` concreto (ver
 * `frontend/src/hooks/useSpeechToText.ts`) baseado na lib `expo-speech-recognition`,
 * substituindo o `unsupportedRecognizer` stub.
 *
 * Os testes de plataforma (grupo "card #75") cobrem os critérios de aceite
 * específicos do card #75 (Reconhecimento de voz nativo no iOS e Android):
 * pt-BR explícito no `start()`, erro de "microfone ocupado" tratado sem
 * lançar exceção, e `isAvailable()` sempre `false` no web.
 */
import type { ExpoSpeechRecognitionResultEvent } from 'expo-speech-recognition';

type Listener<T> = (event: T) => void;

const listeners: Record<string, Listener<unknown>[]> = {};

const addListener = jest.fn((event: string, cb: Listener<unknown>) => {
  listeners[event] = listeners[event] ?? [];
  listeners[event].push(cb);
  return {
    remove: jest.fn(() => {
      listeners[event] = (listeners[event] ?? []).filter((l) => l !== cb);
    }),
  };
});

function emit<T>(event: string, payload: T) {
  (listeners[event] ?? []).forEach((cb) => cb(payload));
}

const isRecognitionAvailable = jest.fn(() => true);
const requestPermissionsAsync = jest.fn();
const start = jest.fn();
const stop = jest.fn();

jest.mock('expo-speech-recognition', () => ({
  ExpoSpeechRecognitionModule: {
    isRecognitionAvailable,
    requestPermissionsAsync,
    start,
    stop,
    addListener,
  },
}));

// `react-native` real usa sintaxe Flow que o projeto ts-jest (testEnvironment
// 'node') não consegue transformar; mocka-se um `Platform` mínimo e mutável
// (mesmo padrão usado em DashboardScreen.platformRender.test.tsx) para poder
// alternar 'ios'/'android'/'web' entre os testes.
jest.mock('react-native', () => ({ Platform: { OS: 'ios' } }));

import { Platform } from 'react-native';
import { expoSpeechRecognizer } from '../expoSpeechRecognizer';

describe('expoSpeechRecognizer', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    Object.keys(listeners).forEach((key) => delete listeners[key]);
    isRecognitionAvailable.mockReturnValue(true);
    Platform.OS = 'ios';
  });

  it('isAvailable reflete ExpoSpeechRecognitionModule.isRecognitionAvailable()', () => {
    isRecognitionAvailable.mockReturnValue(true);
    expect(expoSpeechRecognizer.isAvailable()).toBe(true);

    isRecognitionAvailable.mockReturnValue(false);
    expect(expoSpeechRecognizer.isAvailable()).toBe(false);
  });

  it('isAvailable não lança quando o módulo nativo falha', () => {
    isRecognitionAvailable.mockImplementation(() => {
      throw new Error('módulo nativo indisponível');
    });
    expect(expoSpeechRecognizer.isAvailable()).toBe(false);
  });

  it('card #75: isAvailable é sempre false no web, mesmo que o módulo diga que sim', () => {
    Platform.OS = 'web';
    isRecognitionAvailable.mockReturnValue(true);

    expect(expoSpeechRecognizer.isAvailable()).toBe(false);
    // Nem chega a consultar o módulo nativo: a plataforma já basta para negar.
    expect(isRecognitionAvailable).not.toHaveBeenCalled();
  });

  it.each(['ios', 'android'])(
    'card #75: isAvailable em %s reflete o módulo nativo normalmente',
    (os) => {
      Platform.OS = os as typeof Platform.OS;
      isRecognitionAvailable.mockReturnValue(true);
      expect(expoSpeechRecognizer.isAvailable()).toBe(true);
    }
  );

  it('requestPermission resolve true quando a permissão é concedida', async () => {
    requestPermissionsAsync.mockResolvedValue({ granted: true });
    await expect(expoSpeechRecognizer.requestPermission()).resolves.toBe(true);
  });

  it('requestPermission resolve false quando a permissão é negada', async () => {
    requestPermissionsAsync.mockResolvedValue({ granted: false });
    await expect(expoSpeechRecognizer.requestPermission()).resolves.toBe(false);
  });

  it('start() dispara o reconhecimento nativo e repassa o resultado final', async () => {
    const onResult = jest.fn();
    const onError = jest.fn();
    const onEnd = jest.fn();

    await expoSpeechRecognizer.start({ onResult, onError, onEnd });

    // Card #75: locale deve ser explicitamente pt-BR, não qualquer string.
    expect(start).toHaveBeenCalledWith(
      expect.objectContaining({ lang: 'pt-BR' })
    );

    // Resultado parcial não deve disparar onResult.
    emit<ExpoSpeechRecognitionResultEvent>('result', {
      isFinal: false,
      results: [{ transcript: 'parcial', confidence: 0.5, segments: [] }],
    });
    expect(onResult).not.toHaveBeenCalled();

    // Resultado final dispara onResult com a transcrição.
    emit<ExpoSpeechRecognitionResultEvent>('result', {
      isFinal: true,
      results: [{ transcript: 'tomar remédio às 8h', confidence: 0.9, segments: [] }],
    });
    expect(onResult).toHaveBeenCalledWith('tomar remédio às 8h');

    emit('end', null);
    expect(onEnd).toHaveBeenCalled();
    expect(onError).not.toHaveBeenCalled();
  });

  it('start() repassa erros do reconhecedor nativo via onError', async () => {
    const onResult = jest.fn();
    const onError = jest.fn();

    await expoSpeechRecognizer.start({ onResult, onError });

    emit('error', { error: 'no-speech', message: 'nenhuma fala detectada' });

    expect(onError).toHaveBeenCalledTimes(1);
    expect(onResult).not.toHaveBeenCalled();
  });

  it('card #75: erro de permissão negada é repassado via requestPermission (não lança)', async () => {
    requestPermissionsAsync.mockResolvedValue({ granted: false });
    await expect(expoSpeechRecognizer.requestPermission()).resolves.toBe(false);
  });

  it('card #75: erro de microfone ocupado é repassado via onError sem lançar exceção', async () => {
    const onResult = jest.fn();
    const onError = jest.fn();

    await expect(
      expoSpeechRecognizer.start({ onResult, onError })
    ).resolves.toBeUndefined();

    expect(() =>
      emit('error', {
        error: 'audio-capture',
        message: 'microfone em uso por outro app',
      })
    ).not.toThrow();

    expect(onError).toHaveBeenCalledTimes(1);
    expect(onError).toHaveBeenCalledWith(
      expect.objectContaining({ message: 'microfone em uso por outro app' })
    );
    expect(onResult).not.toHaveBeenCalled();
  });

  it('stop() chama ExpoSpeechRecognitionModule.stop()', async () => {
    await expoSpeechRecognizer.stop();
    expect(stop).toHaveBeenCalledTimes(1);
  });
});
