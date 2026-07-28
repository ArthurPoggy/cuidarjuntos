import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useCallback } from 'react';
import { chatApi } from '../api/endpoints';
import { useAuth } from '../contexts/AuthContext';
import type { ChatConsentState } from '../types/models';

/**
 * Consentimento explícito para o uso da assistente de IA.
 *
 * A conversa envia dados sensíveis de saúde (nome/observações do paciente e
 * registros recentes do grupo) para um serviço externo (Anthropic). Por isso o
 * aceite **mora no backend**, não no dispositivo: o endpoint `/chat/` recusa o
 * envio com `403 CONSENT_REQUIRED` enquanto não houver aceite registrado — um
 * cliente adulterado ou uma chamada direta à API não conseguem burlar o gate.
 * A UI daqui é conveniência; a barreira de verdade é o servidor.
 *
 * O aceite é escopado por **usuário + grupo de cuidado** (quem cuida de outro
 * paciente consente de novo) e versionado: se o texto do aviso mudar, sobe-se
 * `CHAT_CONSENT_VERSION` no backend e todos precisam aceitar outra vez.
 */
export const chatConsentKey = (groupId?: number | null) =>
  ['chat', 'consent', groupId ?? 'none'] as const;

export type ChatConsentStatus =
  | 'loading'
  /** Sem usuário ou sem grupo atual: não há o que consentir. */
  | 'unavailable'
  | 'granted'
  | 'required'
  /** Não deu para saber o estado (rede/servidor). Falha fechada: não envia. */
  | 'error';

export interface ChatConsent {
  status: ChatConsentStatus;
  /** ISO do momento do aceite, quando houver. */
  acceptedAt: string | null;
  /** true enquanto grava/revoga o aceite no servidor. */
  isMutating: boolean;
  /** Rejeita se a gravação falhar — quem chama trata o erro. */
  accept: () => Promise<void>;
  revoke: () => Promise<void>;
  refetch: () => void;
}

export function useChatConsent(): ChatConsent {
  const queryClient = useQueryClient();
  const { user, group } = useAuth();
  const groupId = group?.id ?? null;
  const enabled = user != null && groupId != null;
  const key = chatConsentKey(groupId);

  const query = useQuery({
    queryKey: key,
    queryFn: async (): Promise<ChatConsentState> => {
      const { data } = await chatApi.getConsent();
      return data;
    },
    enabled,
    staleTime: 5 * 60 * 1000,
  });

  const acceptMutation = useMutation({
    mutationFn: async () => {
      const { data } = await chatApi.acceptConsent();
      return data;
    },
    onSuccess: (data) => queryClient.setQueryData(key, data),
  });

  const revokeMutation = useMutation({
    mutationFn: () => chatApi.revokeConsent(),
    onSuccess: () =>
      queryClient.setQueryData<ChatConsentState>(key, (current) => ({
        granted: false,
        accepted_at: null,
        version: current?.version ?? 0,
      })),
  });

  // `mutateAsync` rejeita em caso de falha: a tela decide o que mostrar, em vez
  // de o hook engolir o erro e deixar o botão travado sem feedback.
  const accept = useCallback(async () => {
    await acceptMutation.mutateAsync();
  }, [acceptMutation]);

  const revoke = useCallback(async () => {
    await revokeMutation.mutateAsync();
  }, [revokeMutation]);

  const refetch = useCallback(() => {
    query.refetch();
  }, [query]);

  let status: ChatConsentStatus;
  if (!enabled) {
    status = 'unavailable';
  } else if (query.isPending) {
    status = 'loading';
  } else if (query.isError) {
    // Na dúvida, não libera o envio — o backend recusaria de qualquer forma.
    status = 'error';
  } else {
    status = query.data?.granted ? 'granted' : 'required';
  }

  return {
    status,
    acceptedAt: query.data?.accepted_at ?? null,
    isMutating: acceptMutation.isPending || revokeMutation.isPending,
    accept,
    revoke,
    refetch,
  };
}
