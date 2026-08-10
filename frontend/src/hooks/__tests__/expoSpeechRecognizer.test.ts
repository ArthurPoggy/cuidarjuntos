/**
 * Testes para o item do card #77 "Adicionar biblioteca de reconhecimento de
 * voz": registrar um `SpeechRecognizer` concreto (ver
 * `frontend/src/hooks/useSpeechToText.ts`) baseado na lib `expo-speech-recognition`,
 * substituindo o `unsupportedRecognizer` stub.
 *
 * Este arquivo testa `frontend/src/hooks/expoSpeechRecognizer.ts`, um adaptador
 * ainda inexistente. Até ele ser criado, todos os testes abaixo falham por
 * "Cannot find module '../expoSpeechRecognizer'" -- essa é a falha esperada
 * nesta etapa (somente testes, sem implementação).
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

import { expoSpeechRecognizer } from '../expoSpeechRecognizer';

describe('expoSpeechRecognizer', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    Object.keys(listeners).forEach((key) => delete listeners[key]);
    isRecognitionAvailable.mockReturnValue(true);
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

    expect(start).toHaveBeenCalledWith(
      expect.objectContaining({ lang: expect.any(String) })
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

  it('stop() chama ExpoSpeechRecognitionModule.stop()', async () => {
    await expoSpeechRecognizer.stop();
    expect(stop).toHaveBeenCalledTimes(1);
  });
});
