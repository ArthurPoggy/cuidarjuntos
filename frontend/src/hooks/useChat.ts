import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Alert } from 'react-native';
import { chatApi } from '../api/endpoints';
import type { ChatMessage } from '../types/models';

export const CHAT_HISTORY_KEY = ['chat', 'history'] as const;

/**
 * Histórico de conversa do usuário no grupo atual.
 * staleTime: 0 → sempre busca fresh ao montar a tela.
 */
export function useChatHistory() {
  return useQuery({
    queryKey: CHAT_HISTORY_KEY,
    queryFn: async (): Promise<ChatMessage[]> => {
      const { data } = await chatApi.history();
      return data.results;
    },
    staleTime: 0,
  });
}

interface SendContext {
  previous: ChatMessage[];
  optimisticId: number;
}

/**
 * Envia uma mensagem para a IA com atualização otimista:
 * a mensagem do usuário entra no cache na hora; ao receber a resposta, ela é
 * confirmada e a mensagem da IA é anexada. Em caso de erro, faz rollback e avisa.
 */
export function useSendMessage() {
  const queryClient = useQueryClient();

  return useMutation<string, unknown, string, SendContext>({
    mutationFn: async (message: string) => {
      const { data } = await chatApi.send(message);
      return data.reply;
    },
    onMutate: async (message: string) => {
      await queryClient.cancelQueries({ queryKey: CHAT_HISTORY_KEY });
      const previous = queryClient.getQueryData<ChatMessage[]>(CHAT_HISTORY_KEY) ?? [];

      const optimisticId = -Date.now();
      const optimistic: ChatMessage = {
        id: optimisticId,
        role: 'user',
        content: message,
        created_at: new Date().toISOString(),
        pending: true,
      };
      queryClient.setQueryData<ChatMessage[]>(CHAT_HISTORY_KEY, [...previous, optimistic]);

      return { previous, optimisticId };
    },
    onSuccess: (reply, _message, context) => {
      const assistant: ChatMessage = {
        id: -(Date.now() + 1),
        role: 'assistant',
        content: reply,
        created_at: new Date().toISOString(),
      };
      queryClient.setQueryData<ChatMessage[]>(CHAT_HISTORY_KEY, (current = []) => {
        const confirmed = current.map((m) =>
          m.id === context?.optimisticId ? { ...m, pending: false } : m
        );
        return [...confirmed, assistant];
      });
    },
    onError: (_error, _message, context) => {
      if (context?.previous) {
        queryClient.setQueryData<ChatMessage[]>(CHAT_HISTORY_KEY, context.previous);
      }
      Alert.alert('Erro', 'Não consegui enviar sua mensagem. Tente novamente.');
    },
  });
}
