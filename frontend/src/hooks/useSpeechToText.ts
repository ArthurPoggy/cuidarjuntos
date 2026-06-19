import { useCallback, useState } from 'react';

export type SpeechStatus = 'idle' | 'recording' | 'processing' | 'error';

export interface SpeechRecognizerHandlers {
  onResult: (text: string) => void;
  onError: (err: unknown) => void;
  onEnd?: () => void;
}

/**
 * Contrato do reconhecedor de voz nativo. Um adaptador concreto (ex.:
 * @react-native-voice/voice ou expo-speech-recognition) é injetado pelos cards
 * de reconhecimento nativo (#75/#77) via `setSpeechRecognizer`. Mantém este
 * hook desacoplado da lib específica.
 */
export interface SpeechRecognizer {
  isAvailable(): boolean;
  requestPermission(): Promise<boolean>;
  start(handlers: SpeechRecognizerHandlers): Promise<void>;
  stop(): Promise<void>;
}

// Stub padrão: ainda não há reconhecedor nativo instalado no projeto.
// Falha de forma graciosa em vez de quebrar quem usa o hook.
const unsupportedRecognizer: SpeechRecognizer = {
  isAvailable: () => false,
  requestPermission: async () => false,
  start: async () => {
    throw new Error('Reconhecimento de voz não está disponível neste dispositivo.');
  },
  stop: async () => {},
};

let activeRecognizer: SpeechRecognizer = unsupportedRecognizer;

/** Registra o reconhecedor de voz concreto (chamado uma vez no bootstrap do app). */
export function setSpeechRecognizer(recognizer: SpeechRecognizer): void {
  activeRecognizer = recognizer;
}

export interface UseSpeechToText {
  status: SpeechStatus;
  error: unknown;
  isRecording: boolean;
  start: (onResult: (text: string) => void) => Promise<void>;
  stop: () => Promise<void>;
}

/**
 * Encapsula o ciclo de captura de voz (idle → recording → processing → error)
 * e expõe uma interface simples para qualquer campo de texto.
 */
export function useSpeechToText(onError?: (err: unknown) => void): UseSpeechToText {
  const [status, setStatus] = useState<SpeechStatus>('idle');
  const [error, setError] = useState<unknown>(null);

  const fail = useCallback(
    (err: unknown) => {
      setError(err);
      setStatus('error');
      onError?.(err);
    },
    [onError]
  );

  const start = useCallback(
    async (onResult: (text: string) => void) => {
      setError(null);

      if (!activeRecognizer.isAvailable()) {
        fail(new Error('Reconhecimento de voz não está disponível neste dispositivo.'));
        return;
      }

      const granted = await activeRecognizer.requestPermission();
      if (!granted) {
        fail(new Error('Permissão de microfone negada.'));
        return;
      }

      setStatus('recording');
      try {
        await activeRecognizer.start({
          onResult: (text: string) => {
            setStatus('processing');
            onResult(text);
            setStatus('idle');
          },
          onError: (err: unknown) => fail(err),
          // Ao encerrar o reconhecimento, volta para idle a menos que tenha
          // havido erro. Cobre tanto o fim natural (estava 'recording') quanto
          // o fim após stop() (estava 'processing'), evitando ficar preso.
          onEnd: () => setStatus((prev) => (prev === 'error' ? prev : 'idle')),
        });
      } catch (err) {
        fail(err);
      }
    },
    [fail]
  );

  const stop = useCallback(async () => {
    // Só transiciona para 'processing' se estávamos gravando. O retorno ao
    // 'idle' fica a cargo de onResult/onEnd; se o stop falhar, vai para 'error'.
    setStatus((prev) => (prev === 'recording' ? 'processing' : prev));
    try {
      await activeRecognizer.stop();
    } catch (err) {
      fail(err);
    }
  }, [fail]);

  return {
    status,
    error,
    isRecording: status === 'recording',
    start,
    stop,
  };
}
