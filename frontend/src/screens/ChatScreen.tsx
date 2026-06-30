import React, { useMemo, useRef, useState } from 'react';
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  StyleSheet,
  FlatList,
  ActivityIndicator,
  KeyboardAvoidingView,
  Platform,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { colors, spacing, fontSize, borderRadius } from '../theme';
import { useChatHistory, useSendMessage } from '../hooks/useChat';
import { useSpeechToText } from '../hooks/useSpeechToText';
import MicrophoneButton from '../components/MicrophoneButton';
import type { ChatMessage } from '../types/models';

const WELCOME: ChatMessage = {
  id: -1,
  role: 'assistant',
  content:
    'Olá! Sou a assistente do CuidarJuntos. Posso ajudar a resumir os registros, ' +
    'lembrar de cuidados e tirar dúvidas sobre o dia a dia do paciente. Como posso ajudar?',
  created_at: '',
};

function formatTime(iso: string): string {
  if (!iso) return '';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '';
  return d.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' });
}

function MessageBubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === 'user';
  return (
    <View style={[styles.bubbleRow, isUser ? styles.rowEnd : styles.rowStart]}>
      <View style={[styles.bubble, isUser ? styles.bubbleUser : styles.bubbleAssistant]}>
        <Text style={isUser ? styles.textUser : styles.textAssistant}>{message.content}</Text>
        <View style={styles.metaRow}>
          {message.pending ? (
            <Text style={[styles.timestamp, isUser && styles.timestampUser]}>enviando…</Text>
          ) : (
            <Text style={[styles.timestamp, isUser && styles.timestampUser]}>
              {formatTime(message.created_at)}
            </Text>
          )}
        </View>
      </View>
    </View>
  );
}

export default function ChatScreen() {
  const { data: history = [], isLoading, isError, refetch, isRefetching } = useChatHistory();
  const sendMessage = useSendMessage();
  // Só lemos a disponibilidade aqui; o controle do ciclo de voz fica no botão.
  const { isAvailable: voiceAvailable } = useSpeechToText();
  const [text, setText] = useState('');
  const listRef = useRef<FlatList<ChatMessage>>(null);

  const handleVoiceResult = (spoken: string) => {
    setText((prev) => (prev ? `${prev} ${spoken}` : spoken).trim());
  };

  const messages = useMemo<ChatMessage[]>(
    () => (history.length > 0 ? history : [WELCOME]),
    [history]
  );

  const scrollToEnd = () => {
    requestAnimationFrame(() => listRef.current?.scrollToEnd({ animated: true }));
  };

  const handleSend = () => {
    const trimmed = text.trim();
    if (!trimmed || sendMessage.isPending) return;
    sendMessage.mutate(trimmed, { onSuccess: scrollToEnd });
    setText('');
    scrollToEnd();
  };

  // "Atualizar" busca o histórico real do backend. Não oferecemos "apagar"
  // aqui porque o histórico fica persistido no servidor; uma exclusão real
  // exige um endpoint dedicado (follow-up) para não dar falsa impressão de
  // remoção de dados sensíveis de saúde.
  const handleRefresh = () => {
    refetch();
  };

  return (
    <SafeAreaView style={styles.container} edges={['bottom']}>
      <View style={styles.topBar}>
        <Text style={styles.topTitle}>Assistente</Text>
        <TouchableOpacity onPress={handleRefresh} hitSlop={8} disabled={isRefetching}>
          <Text style={styles.refreshButton}>{isRefetching ? 'Atualizando…' : 'Atualizar'}</Text>
        </TouchableOpacity>
      </View>

      <View style={styles.disclaimer}>
        <Text style={styles.disclaimerText}>
          Respostas geradas por IA (Anthropic) com base nos dados do paciente.
          Não substitui avaliação ou orientação de um profissional de saúde.
        </Text>
      </View>

      <KeyboardAvoidingView
        style={styles.flex}
        behavior={Platform.OS === 'ios' ? 'padding' : undefined}
        keyboardVerticalOffset={Platform.OS === 'ios' ? 90 : 0}
      >
        {isLoading ? (
          <View style={styles.center}>
            <ActivityIndicator size="large" color={colors.primary} />
          </View>
        ) : isError ? (
          <View style={styles.center}>
            <Text style={styles.errorText}>Não consegui carregar a conversa.</Text>
            <TouchableOpacity style={styles.retryButton} onPress={handleRefresh} activeOpacity={0.7}>
              <Text style={styles.retryButtonText}>Tentar novamente</Text>
            </TouchableOpacity>
          </View>
        ) : (
          <FlatList
            ref={listRef}
            data={messages}
            keyExtractor={(item) => String(item.id)}
            renderItem={({ item }) => <MessageBubble message={item} />}
            contentContainerStyle={styles.listContent}
            onContentSizeChange={scrollToEnd}
            keyboardShouldPersistTaps="handled"
          />
        )}

        <View style={styles.inputBar}>
          <TextInput
            style={styles.input}
            value={text}
            onChangeText={setText}
            placeholder="Escreva sua mensagem…"
            placeholderTextColor={colors.textMuted}
            multiline
            editable={!sendMessage.isPending}
          />
          {voiceAvailable && (
            <MicrophoneButton onResult={handleVoiceResult} size={22} />
          )}
          <TouchableOpacity
            style={[styles.sendButton, (!text.trim() || sendMessage.isPending) && styles.sendButtonDisabled]}
            onPress={handleSend}
            disabled={!text.trim() || sendMessage.isPending}
            activeOpacity={0.7}
          >
            {sendMessage.isPending ? (
              <ActivityIndicator size="small" color={colors.textInverse} />
            ) : (
              <Text style={styles.sendButtonText}>Enviar</Text>
            )}
          </TouchableOpacity>
        </View>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  flex: { flex: 1 },
  center: { flex: 1, justifyContent: 'center', alignItems: 'center', padding: spacing.lg },
  topBar: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    backgroundColor: colors.surface,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  topTitle: { fontSize: fontSize.lg, fontWeight: '700', color: colors.text },
  refreshButton: { fontSize: fontSize.sm, color: colors.primary, fontWeight: '600' },
  disclaimer: {
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    backgroundColor: colors.background,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  disclaimerText: { fontSize: fontSize.xs, color: colors.textMuted },
  errorText: { fontSize: fontSize.md, color: colors.text, marginBottom: spacing.md, textAlign: 'center' },
  retryButton: {
    backgroundColor: colors.primary,
    borderRadius: borderRadius.lg,
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.sm,
  },
  retryButtonText: { color: colors.textInverse, fontWeight: '600', fontSize: fontSize.md },
  listContent: { padding: spacing.md, gap: spacing.sm },
  bubbleRow: { flexDirection: 'row' },
  rowEnd: { justifyContent: 'flex-end' },
  rowStart: { justifyContent: 'flex-start' },
  bubble: {
    maxWidth: '82%',
    paddingVertical: spacing.sm,
    paddingHorizontal: spacing.md,
    borderRadius: borderRadius.lg,
  },
  bubbleUser: { backgroundColor: colors.primary, borderBottomRightRadius: borderRadius.sm },
  bubbleAssistant: { backgroundColor: colors.surface, borderBottomLeftRadius: borderRadius.sm, borderWidth: 1, borderColor: colors.border },
  textUser: { color: colors.textInverse, fontSize: fontSize.md },
  textAssistant: { color: colors.text, fontSize: fontSize.md },
  metaRow: { marginTop: 2, alignItems: 'flex-end' },
  timestamp: { fontSize: fontSize.xs, color: colors.textMuted },
  timestampUser: { color: 'rgba(255,255,255,0.7)' },
  inputBar: {
    flexDirection: 'row',
    alignItems: 'flex-end',
    padding: spacing.sm,
    backgroundColor: colors.surface,
    borderTopWidth: 1,
    borderTopColor: colors.border,
    gap: spacing.sm,
  },
  input: {
    flex: 1,
    maxHeight: 120,
    minHeight: 44,
    paddingHorizontal: spacing.md,
    paddingTop: spacing.sm,
    paddingBottom: spacing.sm,
    backgroundColor: colors.background,
    borderRadius: borderRadius.lg,
    borderWidth: 1,
    borderColor: colors.border,
    color: colors.text,
    fontSize: fontSize.md,
  },
  sendButton: {
    backgroundColor: colors.primary,
    borderRadius: borderRadius.lg,
    paddingHorizontal: spacing.lg,
    height: 44,
    justifyContent: 'center',
    alignItems: 'center',
    minWidth: 72,
  },
  sendButtonDisabled: { backgroundColor: colors.textMuted },
  sendButtonText: { color: colors.textInverse, fontWeight: '600', fontSize: fontSize.md },
});
