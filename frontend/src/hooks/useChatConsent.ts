import AsyncStorage from '@react-native-async-storage/async-storage';
import { useCallback, useEffect, useState } from 'react';
import { useAuth } from '../contexts/AuthContext';

/**
 * Consentimento explícito para o uso da assistente de IA.
 *
 * A conversa envia dados sensíveis de saúde (nome/observações do paciente e
 * registros recentes do grupo) para um serviço externo (Anthropic). Por isso o
 * aceite é: explícito (o usuário precisa tocar em "Aceitar"), persistido (não
 * pergunta de novo a cada abertura) e escopado por **usuário + grupo de
 * cuidado** — quem cuida de outro paciente precisa consentir de novo, e o
 * aceite de um usuário não vale para outro no mesmo aparelho.
 *
 * Se o texto do aviso mudar, basta subir a `CHAT_CONSENT_VERSION` para exigir
 * um novo aceite de todo mundo.
 */
export const CHAT_CONSENT_VERSION = 1;

export const chatConsentKey = (userId: number, groupId: number) =>
  `chat_consent:v${CHAT_CONSENT_VERSION}:${userId}:${groupId}`;

export type ChatConsentStatus = 'loading' | 'granted' | 'required' | 'unavailable';

export interface ChatConsent {
  /** `unavailable` = sem usuário ou sem grupo atual; não há o que consentir. */
  status: ChatConsentStatus;
  /** ISO do momento do aceite, quando houver. */
  acceptedAt: string | null;
  accept: () => Promise<void>;
  revoke: () => Promise<void>;
}

export function useChatConsent(): ChatConsent {
  const { user, group } = useAuth();
  const userId = user?.id ?? null;
  const groupId = group?.id ?? null;
  const [status, setStatus] = useState<ChatConsentStatus>('loading');
  const [acceptedAt, setAcceptedAt] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    if (userId == null || groupId == null) {
      setStatus('unavailable');
      setAcceptedAt(null);
      return;
    }

    setStatus('loading');
    (async () => {
      try {
        const stored = await AsyncStorage.getItem(chatConsentKey(userId, groupId));
        if (cancelled) return;
        setAcceptedAt(stored);
        setStatus(stored ? 'granted' : 'required');
      } catch {
        // Na dúvida, pede o aceite de novo: nunca liberar envio sem consentimento.
        if (cancelled) return;
        setAcceptedAt(null);
        setStatus('required');
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [userId, groupId]);

  const accept = useCallback(async () => {
    if (userId == null || groupId == null) return;
    const now = new Date().toISOString();
    await AsyncStorage.setItem(chatConsentKey(userId, groupId), now);
    setAcceptedAt(now);
    setStatus('granted');
  }, [userId, groupId]);

  const revoke = useCallback(async () => {
    if (userId == null || groupId == null) return;
    await AsyncStorage.removeItem(chatConsentKey(userId, groupId));
    setAcceptedAt(null);
    setStatus('required');
  }, [userId, groupId]);

  return { status, acceptedAt, accept, revoke };
}
