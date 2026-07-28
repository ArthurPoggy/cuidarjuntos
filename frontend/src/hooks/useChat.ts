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
  /** `null` quando não há grupo atual: nada foi escrito no cache. */
  optimisticId: number | null;
}

/**
 * Gerador de IDs otimistas locais: sempre negativos (para nunca colidir com os
 * IDs reais, positivos, vindos do backend) e monotonicamente decrescentes.
 * Substitui `-Date.now()`, que podia repetir em envios no mesmo milissegundo.
 */
let optimisticSeq = 0;
const nextOptimisticId = () => {
  optimisticSeq -= 1;
  return optimisticSeq;
};

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
      // Sem grupo atual não há contexto de cuidado para a IA: não envia.
      if (groupId == null) {
        throw new Error('Nenhum grupo de cuidado selecionado.');
      }
      const { data } = await chatApi.send(message);
      return data.reply;
    },
    onMutate: async (message: string) => {
      // Sem grupo atual o `mutationFn` já vai falhar: não mexe no cache, para
      // não criar uma mensagem temporária na key 'none' (que não corresponde a
      // nenhum histórico real) só para removê-la logo em seguida.
      if (groupId == null) {
        return { optimisticId: null };
      }
      await queryClient.cancelQueries({ queryKey: key });
      const optimisticId = nextOptimisticId();
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
        id: nextOptimisticId(),
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
      if (context?.optimisticId != null) {
        // Remove apenas a mensagem otimista desta mutação — não restaura o cache
        // inteiro, para não sobrescrever outras mutações concorrentes.
        queryClient.setQueryData<ChatMessage[]>(key, (current = []) =>
          current.filter((m) => m.id !== context.optimisticId)
        );
      }
      Alert.alert(
        'Erro',
        groupId == null
          ? 'Selecione um grupo de cuidado antes de conversar com a assistente.'
          : 'Não consegui enviar sua mensagem. Tente novamente.'
      );
    },
    onSettled: () => {
      // Sem grupo não há query habilitada para reconciliar (ver `useChatHistory`).
      if (groupId == null) {
        return;
      }
      // Reconcilia com o backend: substitui as entradas otimistas (IDs/timestamps
      // locais) pelos dados reais persistidos.
      queryClient.invalidateQueries({ queryKey: key });
    },
  });
}
