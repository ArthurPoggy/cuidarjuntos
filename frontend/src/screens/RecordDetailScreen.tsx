import React, { useCallback, useEffect, useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ActivityIndicator,
  FlatList,
  TouchableOpacity,
  TextInput,
  Alert,
  ScrollView,
  RefreshControl,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useNavigation, useRoute } from '@react-navigation/native';
import { recordsApi } from '../api/endpoints';
import { colors, spacing, fontSize, borderRadius } from '../theme';
import { CATEGORY_META, REACTION_OPTIONS } from '../utils/constants';
import type { CareRecord, RecordComment, SocialSummary } from '../types/models';

const STATUS_COLORS: Record<string, string> = {
  pending: colors.statusPending,
  done: colors.statusDone,
  missed: colors.statusMissed,
};

const STATUS_LABELS: Record<string, string> = {
  pending: 'Pendente',
  done: 'Feito',
  missed: 'Perdido',
};

export default function RecordDetailScreen() {
  const navigation = useNavigation<any>();
  const route = useRoute<any>();
  const recordId: number = route.params?.id;

  const [record, setRecord] = useState<CareRecord | null>(null);
  const [comments, setComments] = useState<RecordComment[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState('');
  const [commentText, setCommentText] = useState('');
  const [sendingComment, setSendingComment] = useState(false);
  const [reactingTo, setReactingTo] = useState('');

  const fetchRecord = useCallback(async () => {
    try {
      setError('');
      const [recordRes, commentsRes] = await Promise.all([
        recordsApi.get(recordId),
        recordsApi.getComments(recordId),
      ]);
      setRecord(recordRes.data);
      setComments(commentsRes.data);
    } catch {
      setError('Erro ao carregar detalhes do registro.');
    }
  }, [recordId]);

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      await fetchRecord();
      setLoading(false);
    };
    load();
  }, [fetchRecord]);

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    await fetchRecord();
    setRefreshing(false);
  }, [fetchRecord]);

  const handleReact = async (reaction: string) => {
    if (reactingTo) return;
    setReactingTo(reaction);
    try {
      await recordsApi.react(recordId, reaction);
      await fetchRecord();
    } catch {
      Alert.alert('Erro', 'Nao foi possivel reagir.');
    } finally {
      setReactingTo('');
    }
  };

  const handleAddComment = async () => {
    const text = commentText.trim();
    if (!text) return;
    setSendingComment(true);
    try {
      const res = await recordsApi.addComment(recordId, text);
      setComments((prev) => [...prev, res.data]);
      setCommentText('');
    } catch {
      Alert.alert('Erro', 'Nao foi possivel adicionar o comentario.');
    } finally {
      setSendingComment(false);
    }
  };

  const handleEdit = () => {
    if (!record) return;
    navigation.navigate('RecordCreate', { record });
  };

  const handleDelete = () => {
    Alert.alert(
      'Confirmar exclusao',
      'Tem certeza que deseja excluir este registro?',
      [
        { text: 'Cancelar', style: 'cancel' },
        {
          text: 'Excluir',
          style: 'destructive',
          onPress: async () => {
            try {
              await recordsApi.delete(recordId);
              navigation.goBack();
            } catch {
              Alert.alert('Erro', 'Nao foi possivel excluir o registro.');
            }
          },
        },
      ],
    );
  };

  if (loading) {
    return (
      <SafeAreaView style={styles.safe}>
        <View style={styles.center}>
          <ActivityIndicator size="large" color={colors.primary} />
        </View>
      </SafeAreaView>
    );
  }

  if (error || !record) {
    return (
      <SafeAreaView style={styles.safe}>
        <View style={styles.center}>
          <Text style={styles.errorText}>{error || 'Registro nao encontrado.'}</Text>
          <TouchableOpacity style={styles.retryButton} onPress={onRefresh}>
            <Text style={styles.retryText}>Tentar novamente</Text>
          </TouchableOpacity>
        </View>
      </SafeAreaView>
    );
  }

  const meta = CATEGORY_META[record.type];
  const statusColor = STATUS_COLORS[record.status] ?? colors.textMuted;
  const statusLabel = STATUS_LABELS[record.status] ?? record.status;
  const social: SocialSummary = record.social ?? { counts: {}, user_reaction: '', comments_count: 0 };

  const renderCommentItem = ({ item }: { item: RecordComment }) => (
    <View style={styles.commentCard}>
      <View style={styles.commentHeader}>
        <Text style={styles.commentAuthor}>{item.author}</Text>
        <Text style={styles.commentDate}>
          {new Date(item.created_at).toLocaleDateString('pt-BR')}
        </Text>
      </View>
      <Text style={styles.commentBody}>{item.text}</Text>
    </View>
  );

  return (
    <SafeAreaView style={styles.safe}>
      <FlatList
        data={comments}
        keyExtractor={(item) => String(item.id)}
        renderItem={renderCommentItem}
        contentContainerStyle={styles.listContent}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} colors={[colors.primary]} />
        }
        ListHeaderComponent={
          <View>
            {/* Record detail header */}
            <View style={styles.detailCard}>
              <View style={styles.detailTopRow}>
                <View
                  style={[
                    styles.typeCircle,
                    { backgroundColor: meta?.bg ?? colors.borderLight },
                  ]}
                >
                  <Text style={[styles.typeCircleText, { color: meta?.color ?? colors.text }]}>
                    {meta?.label?.charAt(0) ?? '?'}
                  </Text>
                </View>
                <View style={styles.detailTitleContainer}>
                  <Text style={styles.detailType}>{meta?.label ?? record.type}</Text>
                  <Text style={styles.detailWhat}>{record.what}</Text>
                </View>
                <View style={[styles.statusBadge, { backgroundColor: statusColor }]}>
                  <Text style={styles.statusBadgeText}>{statusLabel}</Text>
                </View>
              </View>

              {/* Detail fields */}
              <View style={styles.fieldRow}>
                <Text style={styles.fieldLabel}>Data:</Text>
                <Text style={styles.fieldValue}>{record.date}</Text>
              </View>
              <View style={styles.fieldRow}>
                <Text style={styles.fieldLabel}>Hora:</Text>
                <Text style={styles.fieldValue}>
                  {record.time ? record.time.slice(0, 5) : '--:--'}
                </Text>
              </View>
              <View style={styles.fieldRow}>
                <Text style={styles.fieldLabel}>Cuidador:</Text>
                <Text style={styles.fieldValue}>{record.author_name || record.caregiver || '---'}</Text>
              </View>
              {record.description ? (
                <View style={styles.fieldRow}>
                  <Text style={styles.fieldLabel}>Descricao:</Text>
                  <Text style={styles.fieldValue}>{record.description}</Text>
                </View>
              ) : null}
              {record.medication_detail ? (
                <View style={styles.fieldRow}>
                  <Text style={styles.fieldLabel}>Medicamento:</Text>
                  <Text style={styles.fieldValue}>{record.medication_detail}</Text>
                </View>
              ) : null}
              {record.capsule_quantity ? (
                <View style={styles.fieldRow}>
                  <Text style={styles.fieldLabel}>Quantidade:</Text>
                  <Text style={styles.fieldValue}>{record.capsule_quantity}</Text>
                </View>
              ) : null}
              {record.progress_trend ? (
                <View style={styles.fieldRow}>
                  <Text style={styles.fieldLabel}>Tendencia:</Text>
                  <Text style={styles.fieldValue}>{record.progress_trend}</Text>
                </View>
              ) : null}
              {record.recurrence && record.recurrence !== 'none' ? (
                <View style={styles.fieldRow}>
                  <Text style={styles.fieldLabel}>Repeticao:</Text>
                  <Text style={styles.fieldValue}>{record.recurrence}</Text>
                </View>
              ) : null}
              {record.is_exception && (
                <View style={styles.fieldRow}>
                  <Text style={styles.fieldLabel}>Excecao:</Text>
                  <Text style={styles.fieldValue}>Sim</Text>
                </View>
              )}
            </View>

            {/* Reaction bar */}
            <View style={styles.reactionBar}>
              {REACTION_OPTIONS.map((opt) => {
                const count = social.counts?.[opt.code] ?? 0;
                const isActive = social.user_reaction === opt.code;
                return (
                  <TouchableOpacity
                    key={opt.code}
                    style={[styles.reactionButton, isActive && styles.reactionButtonActive]}
                    onPress={() => handleReact(opt.code)}
                    disabled={reactingTo !== ''}
                    activeOpacity={0.7}
                  >
                    {reactingTo === opt.code ? (
                      <ActivityIndicator size="small" color={colors.primary} />
                    ) : (
                      <>
                        <Text style={styles.reactionEmoji}>{opt.emoji}</Text>
                        <Text
                          style={[
                            styles.reactionCount,
                            isActive && styles.reactionCountActive,
                          ]}
                        >
                          {count}
                        </Text>
                      </>
                    )}
                  </TouchableOpacity>
                );
              })}
            </View>

            {/* Action buttons */}
            <View style={styles.actionRow}>
              <TouchableOpacity style={styles.editButton} onPress={handleEdit} activeOpacity={0.7}>
                <Text style={styles.editButtonText}>Editar</Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={styles.deleteButton}
                onPress={handleDelete}
                activeOpacity={0.7}
              >
                <Text style={styles.deleteButtonText}>Excluir</Text>
              </TouchableOpacity>
            </View>

            {/* Comments header */}
            <Text style={styles.sectionTitle}>
              Comentarios ({comments.length})
            </Text>
          </View>
        }
        ListFooterComponent={
          <View style={styles.commentInputRow}>
            <TextInput
              style={styles.commentInput}
              placeholder="Escreva um comentario..."
              placeholderTextColor={colors.textMuted}
              value={commentText}
              onChangeText={setCommentText}
              editable={!sendingComment}
              multiline
            />
            <TouchableOpacity
              style={[
                styles.sendButton,
                (!commentText.trim() || sendingComment) && styles.sendButtonDisabled,
              ]}
              onPress={handleAddComment}
              disabled={!commentText.trim() || sendingComment}
              activeOpacity={0.8}
            >
              {sendingComment ? (
                <ActivityIndicator color={colors.textInverse} size="small" />
              ) : (
                <Text style={styles.sendButtonText}>Enviar</Text>
              )}
            </TouchableOpacity>
          </View>
        }
        ListEmptyComponent={
          <View style={styles.emptyContainer}>
            <Text style={styles.emptyText}>Nenhum comentario ainda.</Text>
          </View>
        }
      />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: {
    flex: 1,
    backgroundColor: colors.background,
  },
  center: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    padding: spacing.lg,
  },
  listContent: {
    padding: spacing.md,
    paddingBottom: spacing.xxl,
  },
  detailCard: {
    backgroundColor: colors.card,
    borderRadius: borderRadius.lg,
    padding: spacing.lg,
    marginBottom: spacing.md,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.08,
    shadowRadius: 8,
    elevation: 3,
  },
  detailTopRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: spacing.md,
  },
  typeCircle: {
    width: 48,
    height: 48,
    borderRadius: 24,
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: spacing.sm,
  },
  typeCircleText: {
    fontSize: fontSize.xl,
    fontWeight: '700',
  },
  detailTitleContainer: {
    flex: 1,
    marginRight: spacing.sm,
  },
  detailType: {
    fontSize: fontSize.xs,
    color: colors.textSecondary,
    fontWeight: '500',
    textTransform: 'uppercase',
  },
  detailWhat: {
    fontSize: fontSize.lg,
    fontWeight: '600',
    color: colors.text,
  },
  statusBadge: {
    paddingHorizontal: spacing.sm,
    paddingVertical: spacing.xs,
    borderRadius: borderRadius.full,
  },
  statusBadgeText: {
    color: colors.textInverse,
    fontSize: fontSize.xs,
    fontWeight: '600',
  },
  fieldRow: {
    flexDirection: 'row',
    marginBottom: spacing.xs,
  },
  fieldLabel: {
    fontSize: fontSize.sm,
    color: colors.textSecondary,
    fontWeight: '500',
    width: 120,
  },
  fieldValue: {
    flex: 1,
    fontSize: fontSize.sm,
    color: colors.text,
  },
  reactionBar: {
    flexDirection: 'row',
    justifyContent: 'center',
    gap: spacing.md,
    marginBottom: spacing.md,
  },
  reactionButton: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.card,
    borderRadius: borderRadius.full,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    borderWidth: 1,
    borderColor: colors.border,
    minWidth: 70,
    justifyContent: 'center',
  },
  reactionButtonActive: {
    borderColor: colors.primary,
    backgroundColor: '#EFF6FF',
  },
  reactionEmoji: {
    fontSize: fontSize.lg,
    marginRight: spacing.xs,
  },
  reactionCount: {
    fontSize: fontSize.sm,
    color: colors.textSecondary,
    fontWeight: '600',
  },
  reactionCountActive: {
    color: colors.primary,
  },
  actionRow: {
    flexDirection: 'row',
    gap: spacing.sm,
    marginBottom: spacing.lg,
  },
  editButton: {
    flex: 1,
    backgroundColor: colors.primary,
    borderRadius: borderRadius.md,
    paddingVertical: spacing.sm + 2,
    alignItems: 'center',
  },
  editButtonText: {
    color: colors.textInverse,
    fontSize: fontSize.md,
    fontWeight: '600',
  },
  deleteButton: {
    flex: 1,
    backgroundColor: colors.surface,
    borderRadius: borderRadius.md,
    paddingVertical: spacing.sm + 2,
    alignItems: 'center',
    borderWidth: 1,
    borderColor: colors.danger,
  },
  deleteButtonText: {
    color: colors.danger,
    fontSize: fontSize.md,
    fontWeight: '600',
  },
  sectionTitle: {
    fontSize: fontSize.lg,
    fontWeight: '600',
    color: colors.text,
    marginBottom: spacing.sm,
  },
  commentCard: {
    backgroundColor: colors.card,
    borderRadius: borderRadius.md,
    padding: spacing.md,
    marginBottom: spacing.sm,
  },
  commentHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginBottom: spacing.xs,
  },
  commentAuthor: {
    fontSize: fontSize.sm,
    fontWeight: '600',
    color: colors.text,
  },
  commentDate: {
    fontSize: fontSize.xs,
    color: colors.textMuted,
  },
  commentBody: {
    fontSize: fontSize.sm,
    color: colors.textSecondary,
    lineHeight: 20,
  },
  commentInputRow: {
    flexDirection: 'row',
    alignItems: 'flex-end',
    gap: spacing.sm,
    marginTop: spacing.md,
  },
  commentInput: {
    flex: 1,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: borderRadius.md,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    fontSize: fontSize.sm,
    color: colors.text,
    maxHeight: 100,
  },
  sendButton: {
    backgroundColor: colors.primary,
    borderRadius: borderRadius.md,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm + 2,
    justifyContent: 'center',
    alignItems: 'center',
    minHeight: 40,
  },
  sendButtonDisabled: {
    backgroundColor: colors.primaryLight,
  },
  sendButtonText: {
    color: colors.textInverse,
    fontSize: fontSize.sm,
    fontWeight: '600',
  },
  emptyContainer: {
    alignItems: 'center',
    paddingVertical: spacing.lg,
  },
  emptyText: {
    fontSize: fontSize.sm,
    color: colors.textSecondary,
  },
  errorText: {
    color: colors.danger,
    fontSize: fontSize.md,
    textAlign: 'center',
    marginBottom: spacing.md,
  },
  retryButton: {
    backgroundColor: colors.primary,
    borderRadius: borderRadius.md,
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.sm,
  },
  retryText: {
    color: colors.textInverse,
    fontSize: fontSize.md,
    fontWeight: '600',
  },
});
