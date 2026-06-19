import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Alert } from 'react-native';
import { chatApi } from '../api/endpoints';
import { useAuth } from '../contexts/AuthContext';
import type { ChatMessage } from '../types/models';

/**
 * Chave do histórico de chat, isolada por grupo de cuidado.
 *
 * Dados de saúde sensíveis NÃO podem ser compartilhados entre grupos/usuários:
 * a chave inclui o id do grupo, e o cache é limpo no logout (ver AuthContext),
 * evitando exibir histórico de outro contexto no mesmo dispositivo.
 */
export const chatHistoryKey = (groupId?: number | null) =>
  ['chat', 'history', groupId ?? 'none'] as const;

/**
 * Disponibilidade do assistente de IA (feature ligada + chave configurada).
 * Usado para condicionar a exposição da feature (ex.: item de menu) sem o
 * usuário precisar abrir a tela para descobrir que está indisponível.
 */
export function useChatAvailable() {
  const { isAuthenticated, hasGroup } = useAuth();
  return useQuery({
    queryKey: ['chat', 'status'],
    queryFn: async (): Promise<boolean> => {
      const { data } = await chatApi.status();
      return !!data.enabled;
    },
    enabled: isAuthenticated && hasGroup,
    staleTime: 5 * 60 * 1000,
  });
}

/**
 * Histórico de conversa do usuário no grupo atual.
 * staleTime: 0 → sempre busca fresh ao montar a tela.
 */
export function useChatHistory() {
  const { group } = useAuth();
  const groupId = group?.id ?? null;
  return useQuery({
    queryKey: chatHistoryKey(groupId),
    queryFn: async (): Promise<ChatMessage[]> => {
      const { data } = await chatApi.history();
      return data.results;
    },
    enabled: groupId != null,
    staleTime: 0,
  });
}

interface SendContext {
  optimisticId: number;
}

/**
 * Envia uma mensagem para a IA com atualização otimista:
 * a mensagem do usuário entra no cache na hora; ao receber a resposta, ela é
 * anexada. Em caso de erro, remove apenas a mensagem otimista desta mutação
 * (sem clobber de mutações concorrentes) e avisa. Em qualquer desfecho, o cache
 * é invalidado para sincronizar com o backend (IDs/timestamps reais).
 */
export function useSendMessage() {
  const queryClient = useQueryClient();
  const { group } = useAuth();
  const groupId = group?.id ?? null;
  const key = chatHistoryKey(groupId);

  return useMutation<string, unknown, string, SendContext>({
    mutationFn: async (message: string) => {
      const { data } = await chatApi.send(message);
      return data.reply;
    },
    onMutate: async (message: string) => {
      await queryClient.cancelQueries({ queryKey: key });
      const optimisticId = -Date.now();
      const optimistic: ChatMessage = {
        id: optimisticId,
        role: 'user',
        content: message,
        created_at: new Date().toISOString(),
        pending: true,
      };
      queryClient.setQueryData<ChatMessage[]>(key, (current = []) => [
        ...current,
        optimistic,
      ]);
      return { optimisticId };
    },
    onSuccess: (reply, _message, context) => {
      const assistant: ChatMessage = {
        id: -(Date.now() + 1),
        role: 'assistant',
        content: reply,
        created_at: new Date().toISOString(),
        pending: true,
      };
      queryClient.setQueryData<ChatMessage[]>(key, (current = []) => {
        const confirmed = current.map((m) =>
          m.id === context?.optimisticId ? { ...m, pending: false } : m
        );
        return [...confirmed, assistant];
      });
    },
    onError: (_error, _message, context) => {
      // Remove apenas a mensagem otimista desta mutação — não restaura o cache
      // inteiro, para não sobrescrever outras mutações concorrentes.
      queryClient.setQueryData<ChatMessage[]>(key, (current = []) =>
        current.filter((m) => m.id !== context?.optimisticId)
      );
      Alert.alert('Erro', 'Não consegui enviar sua mensagem. Tente novamente.');
    },
    onSettled: () => {
      // Reconcilia com o backend: substitui as entradas otimistas (IDs/timestamps
      // locais) pelos dados reais persistidos.
      queryClient.invalidateQueries({ queryKey: key });
    },
  });
}
