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
import { useQueryClient } from '@tanstack/react-query';
import { colors, spacing, fontSize, borderRadius } from '../theme';
import { useChatHistory, useSendMessage, CHAT_HISTORY_KEY } from '../hooks/useChat';
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
  const queryClient = useQueryClient();
  const { data: history = [], isLoading } = useChatHistory();
  const sendMessage = useSendMessage();
  const [text, setText] = useState('');
  const listRef = useRef<FlatList<ChatMessage>>(null);

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

  const handleClear = () => {
    queryClient.setQueryData<ChatMessage[]>(CHAT_HISTORY_KEY, []);
  };

  return (
    <SafeAreaView style={styles.container} edges={['bottom']}>
      <View style={styles.topBar}>
        <Text style={styles.topTitle}>Assistente</Text>
        <TouchableOpacity onPress={handleClear} hitSlop={8}>
          <Text style={styles.clearButton}>Limpar</Text>
        </TouchableOpacity>
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
  center: { flex: 1, justifyContent: 'center', alignItems: 'center' },
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
  clearButton: { fontSize: fontSize.sm, color: colors.primary, fontWeight: '600' },
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
