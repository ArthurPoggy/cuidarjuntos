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
  Alert,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { colors, spacing, fontSize, borderRadius } from '../theme';
import { useChatHistory, useSendMessage } from '../hooks/useChat';
import { useChatConsent } from '../hooks/useChatConsent';
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

/**
 * Tela de consentimento: aparece antes do primeiro envio e detalha exatamente
 * o que sai do app e para onde. Sem tocar em "Aceitar e continuar" o usuário
 * não chega no campo de mensagem — e, mesmo que chegasse, o backend recusa o
 * envio sem o aceite registrado (403 CONSENT_REQUIRED).
 */
function ConsentGate({
  onAccept,
  saving,
}: {
  onAccept: () => Promise<void>;
  saving: boolean;
}) {
  const [failed, setFailed] = useState(false);

  // Se a gravação no servidor falhar, o botão volta a ficar clicável e o erro
  // aparece na tela — sem isso, uma falha de rede deixava o gate travado.
  const handleAccept = () => {
    setFailed(false);
    onAccept().catch(() => setFailed(true));
  };

  return (
    <View style={styles.consentContainer}>
      <Text style={styles.consentTitle}>Antes de começar</Text>
      <Text style={styles.consentText}>
        A assistente é um recurso de inteligência artificial fornecido pela Anthropic.
        Para responder, o CuidarJuntos envia para esse serviço externo:
      </Text>
      <View style={styles.consentList}>
        <Text style={styles.consentItem}>• nome, data de nascimento e observações do paciente;</Text>
        <Text style={styles.consentItem}>• os registros de cuidado mais recentes do grupo;</Text>
        <Text style={styles.consentItem}>• as mensagens que você escrever nesta conversa.</Text>
      </View>
      <Text style={styles.consentText}>
        São dados sensíveis de saúde. As respostas são geradas por IA, podem conter erros e
        não substituem a avaliação de um profissional. Você pode retirar o consentimento a
        qualquer momento em "Privacidade", no topo desta tela.
      </Text>
      {failed && (
        <Text style={styles.consentError}>
          Não consegui registrar seu consentimento. Verifique sua conexão e tente de novo.
        </Text>
      )}
      <TouchableOpacity
        style={[styles.consentButton, saving && styles.sendButtonDisabled]}
        onPress={handleAccept}
        disabled={saving}
        activeOpacity={0.7}
      >
        {saving ? (
          <ActivityIndicator size="small" color={colors.textInverse} />
        ) : (
          <Text style={styles.consentButtonText}>
            {failed ? 'Tentar novamente' : 'Aceitar e continuar'}
          </Text>
        )}
      </TouchableOpacity>
    </View>
  );
}

export default function ChatScreen() {
  const consent = useChatConsent();
  const { data: history = [], isLoading, isError, refetch, isRefetching } = useChatHistory();
  const sendMessage = useSendMessage();
  const [text, setText] = useState('');
  const listRef = useRef<FlatList<ChatMessage>>(null);
  // Só lemos a disponibilidade aqui; o controle do ciclo de voz fica no botão.
  const { isAvailable: voiceAvailable } = useSpeechToText();

  // O texto ditado é anexado ao que já estiver escrito, em vez de substituir.
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
    // Trava de segurança no cliente; o backend também recusa sem o aceite.
    if (consent.status !== 'granted') return;
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

  // Revogar também é uma escrita no servidor e pode falhar: avisa em vez de
  // deixar o usuário achando que retirou o consentimento.
  const handleRevoke = () => {
    consent.revoke().catch(() => {
      Alert.alert('Erro', 'Não consegui retirar seu consentimento agora. Tente novamente.');
    });
  };

  return (
    <SafeAreaView style={styles.container} edges={['bottom']}>
      <View style={styles.topBar}>
        <Text style={styles.topTitle}>Assistente</Text>
        <View style={styles.topActions}>
          {consent.status === 'granted' && (
            <TouchableOpacity onPress={handleRevoke} hitSlop={8} disabled={consent.isMutating}>
              <Text style={styles.refreshButton}>
                {consent.isMutating ? 'Retirando…' : 'Privacidade'}
              </Text>
            </TouchableOpacity>
          )}
          <TouchableOpacity onPress={handleRefresh} hitSlop={8} disabled={isRefetching}>
            <Text style={styles.refreshButton}>{isRefetching ? 'Atualizando…' : 'Atualizar'}</Text>
          </TouchableOpacity>
        </View>
      </View>

      {consent.status === 'loading' ? (
        <View style={styles.center}>
          <ActivityIndicator size="large" color={colors.primary} />
        </View>
      ) : consent.status === 'unavailable' ? (
        <View style={styles.center}>
          <Text style={styles.errorText}>
            Entre em um grupo de cuidado para conversar com a assistente.
          </Text>
        </View>
      ) : consent.status === 'error' ? (
        <View style={styles.center}>
          <Text style={styles.errorText}>
            Não consegui verificar seu consentimento. Sem essa confirmação a conversa
            fica bloqueada.
          </Text>
          <TouchableOpacity style={styles.retryButton} onPress={consent.refetch} activeOpacity={0.7}>
            <Text style={styles.retryButtonText}>Tentar novamente</Text>
          </TouchableOpacity>
        </View>
      ) : consent.status === 'required' ? (
        <ConsentGate onAccept={consent.accept} saving={consent.isMutating} />
      ) : (
        <>
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
        </>
      )}
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
  topActions: { flexDirection: 'row', alignItems: 'center', gap: spacing.md },
  consentContainer: { flex: 1, padding: spacing.lg, gap: spacing.md },
  consentTitle: { fontSize: fontSize.lg, fontWeight: '700', color: colors.text },
  consentText: { fontSize: fontSize.md, color: colors.text, lineHeight: 22 },
  consentList: { gap: spacing.xs, paddingLeft: spacing.xs },
  consentItem: { fontSize: fontSize.md, color: colors.text, lineHeight: 22 },
  consentButton: {
    backgroundColor: colors.primary,
    borderRadius: borderRadius.lg,
    paddingVertical: spacing.md,
    alignItems: 'center',
    marginTop: spacing.sm,
  },
  consentButtonText: { color: colors.textInverse, fontWeight: '700', fontSize: fontSize.md },
  consentError: { fontSize: fontSize.sm, color: colors.danger },
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
