import { Platform } from 'react-native';
import { ExpoSpeechRecognitionModule } from 'expo-speech-recognition';
import type { SpeechRecognizer, SpeechRecognizerHandlers } from './useSpeechToText';

/**
 * Adaptador concreto dos cards #75/#77: implementa o contrato `SpeechRecognizer`
 * (ver `useSpeechToText.ts`) usando a lib `expo-speech-recognition`, que
 * roda tanto no Expo Go quanto em builds nativas via config plugin (já
 * registrado em `app.json`).
 */
const LOCALE = 'pt-BR';

type Subscription = { remove: () => void };

let activeSubscriptions: Subscription[] = [];

function clearSubscriptions() {
  activeSubscriptions.forEach((sub) => sub.remove());
  activeSubscriptions = [];
}

export const expoSpeechRecognizer: SpeechRecognizer = {
  isAvailable(): boolean {
    // Card #75: no web o reconhecimento nativo não é suportado por este
    // adaptador (mesmo que a lib exponha um fallback via Web Speech API no
    // navegador) — a UI deve ocultar o microfone em vez de expor um
    // comportamento inconsistente entre navegadores.
    if (Platform.OS === 'web') {
      return false;
    }
    // O módulo nativo pode lançar em ambientes sem suporte; trata como
    // indisponível em vez de derrubar o app.
    try {
      return ExpoSpeechRecognitionModule.isRecognitionAvailable();
    } catch {
      return false;
    }
  },

  async requestPermission(): Promise<boolean> {
    const result = await ExpoSpeechRecognitionModule.requestPermissionsAsync();
    return result.granted;
  },

  async start(handlers: SpeechRecognizerHandlers): Promise<void> {
    // Uma chamada anterior pode ter deixado listeners presos (ex.: start()
    // chamado de novo sem stop/end anterior ter disparado).
    clearSubscriptions();

    const resultSub = ExpoSpeechRecognitionModule.addListener('result', (event) => {
      if (!event.isFinal) return;
      const transcript = event.results[0]?.transcript ?? '';
      handlers.onResult(transcript);
    });

    const errorSub = ExpoSpeechRecognitionModule.addListener('error', (event) => {
      clearSubscriptions();
      handlers.onError(new Error(event.message || event.error));
    });

    const endSub = ExpoSpeechRecognitionModule.addListener('end', () => {
      clearSubscriptions();
      handlers.onEnd?.();
    });

    activeSubscriptions = [resultSub, errorSub, endSub];

    ExpoSpeechRecognitionModule.start({
      lang: LOCALE,
      interimResults: false,
      continuous: false,
    });
  },

  async stop(): Promise<void> {
    ExpoSpeechRecognitionModule.stop();
  },
};
