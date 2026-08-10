import { ExpoSpeechRecognitionModule } from 'expo-speech-recognition';
import type { SpeechRecognizer, SpeechRecognizerHandlers } from './useSpeechToText';

/**
 * Adaptador concreto do card #77: implementa o contrato `SpeechRecognizer`
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
    // O módulo nativo pode lançar em ambientes sem suporte (ex.: web sem
    // Web Speech API); trata como indisponível em vez de derrubar o app.
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
