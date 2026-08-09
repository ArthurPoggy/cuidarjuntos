import { useCallback, useEffect, useRef, useState } from 'react';

export type SpeechStatus = 'idle' | 'recording' | 'processing' | 'error';

/**
 * Tempo máximo de espera, depois do `stop()`, pelo callback final do adaptador
 * (`onResult`/`onEnd`/`onError`). Se nada chegar, o hook volta sozinho para
 * `idle` — sem isso, um adaptador que não dispara callback deixaria a UI presa
 * em "processando" para sempre.
 */
export const STOP_FALLBACK_MS = 5000;

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
  /**
   * Há um reconhecedor real registrado? Permite à UI ocultar o microfone em vez
   * de expor um recurso que ainda não funciona.
   */
  isAvailable: boolean;
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
  const fallbackTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Espelho síncrono do status. Os callbacks do adaptador e o `stop()` precisam
  // decidir com base no estado ATUAL, e o `status` do closure pode estar velho
  // (ex.: `stop()` chamado no mesmo tick do `start()`).
  const statusRef = useRef<SpeechStatus>('idle');
  const updateStatus = useCallback(
    (next: SpeechStatus | ((prev: SpeechStatus) => SpeechStatus)) => {
      const value = typeof next === 'function' ? next(statusRef.current) : next;
      statusRef.current = value;
      setStatus(value);
    },
    []
  );

  const clearFallback = useCallback(() => {
    if (fallbackTimer.current != null) {
      clearTimeout(fallbackTimer.current);
      fallbackTimer.current = null;
    }
  }, []);

  // Não deixa timer pendente depois que o componente sai da tela.
  useEffect(() => clearFallback, [clearFallback]);

  const fail = useCallback(
    (err: unknown) => {
      clearFallback();
      setError(err);
      updateStatus('error');
      onError?.(err);
    },
    [clearFallback, onError, updateStatus]
  );

  const start = useCallback(
    async (onResult: (text: string) => void) => {
      setError(null);

      if (!activeRecognizer.isAvailable()) {
        fail(new Error('Reconhecimento de voz não está disponível neste dispositivo.'));
        return;
      }

      // O pedido de permissão é código nativo: pode rejeitar (usuário fechou o
      // diálogo, módulo mal configurado) em vez de devolver false.
      let granted = false;
      try {
        granted = await activeRecognizer.requestPermission();
      } catch (err) {
        fail(err);
        return;
      }
      if (!granted) {
        fail(new Error('Permissão de microfone negada.'));
        return;
      }

      updateStatus('recording');
      try {
        await activeRecognizer.start({
          onResult: (text: string) => {
            clearFallback();
            updateStatus('processing');
            onResult(text);
            updateStatus('idle');
          },
          onError: (err: unknown) => fail(err),
          // Ao encerrar o reconhecimento, volta para idle a menos que tenha
          // havido erro. Cobre tanto o fim natural (estava 'recording') quanto
          // o fim após stop() (estava 'processing'), evitando ficar preso.
          onEnd: () => {
            clearFallback();
            updateStatus((prev) => (prev === 'error' ? prev : 'idle'));
          },
        });
      } catch (err) {
        fail(err);
      }
    },
    [clearFallback, fail, updateStatus]
  );

  const stop = useCallback(async () => {
    // Fora de 'recording' não há o que parar: evita transição espúria e um
    // timer inútil quando o botão é tocado duas vezes ou já houve erro.
    if (statusRef.current !== 'recording') {
      return;
    }
    // O retorno ao 'idle' fica a cargo de onResult/onEnd; se o stop falhar,
    // vai para 'error'.
    updateStatus('processing');

    // Rede de segurança armada ANTES do await: se a Promise do adaptador
    // travar (ou nunca resolver) e nenhum callback vier, o hook volta sozinho
    // para 'idle' em STOP_FALLBACK_MS, em vez de ficar preso em 'processing'.
    clearFallback();
    fallbackTimer.current = setTimeout(() => {
      fallbackTimer.current = null;
      updateStatus((prev) => (prev === 'processing' ? 'idle' : prev));
    }, STOP_FALLBACK_MS);

    try {
      await activeRecognizer.stop();
    } catch (err) {
      fail(err);
    }
  }, [clearFallback, fail, updateStatus]);

  return {
    status,
    error,
    isRecording: status === 'recording',
    isAvailable: activeRecognizer.isAvailable(),
    start,
    stop,
  };
}
