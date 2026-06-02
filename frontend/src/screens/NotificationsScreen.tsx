import React, { useState, useCallback } from 'react';
import {
  View, Text, StyleSheet, FlatList, TouchableOpacity,
  ActivityIndicator, RefreshControl,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { useApiQuery } from '../hooks/useApiQuery';
import { notificationsApi } from '../api/endpoints';
import type { Notification, PaginatedResponse } from '../types/models';
import { colors, spacing, fontSize, borderRadius } from '../theme';

const FILTERS = [
  { key: 'all', label: 'Todas' },
  { key: 'unread', label: 'Não lidas' },
] as const;

type Filter = typeof FILTERS[number]['key'];

function formatRelativeDate(iso: string): string {
  const d = new Date(iso);
  const now = new Date();
  const diffMs = now.getTime() - d.getTime();
  const diffMin = Math.floor(diffMs / 60_000);
  if (diffMin < 1) return 'agora mesmo';
  if (diffMin < 60) return `há ${diffMin} min`;
  const diffH = Math.floor(diffMin / 60);
  if (diffH < 24) return `há ${diffH}h`;
  const diffD = Math.floor(diffH / 24);
  if (diffD === 1) return 'ontem';
  if (diffD < 7) return `há ${diffD} dias`;
  return d.toLocaleDateString('pt-BR');
}

export default function NotificationsScreen() {
  const [filter, setFilter] = useState<Filter>('all');
  const [mutating, setMutating] = useState(false);

  const params = filter === 'unread' ? { read: 'false' } : undefined;
  const { data, isLoading, refetch } = useApiQuery<PaginatedResponse<Notification>>(
    () => notificationsApi.list(params),
    [filter]
  );

  const notifications = data?.results ?? [];

  const handleTap = useCallback(
    async (item: Notification) => {
      if (item.read) return;
      try {
        await notificationsApi.markRead(item.id);
        await refetch();
      } catch {
        // silencioso: a UI volta ao estado real no próximo refetch
      }
    },
    [refetch]
  );

  const handleMarkAll = useCallback(async () => {
    setMutating(true);
    try {
      await notificationsApi.markAllRead();
      await refetch();
    } catch {
      // silencioso
    } finally {
      setMutating(false);
    }
  }, [refetch]);

  if (isLoading) {
    return (
      <SafeAreaView style={styles.safe}>
        <View style={styles.center}>
          <ActivityIndicator size="large" color={colors.primary} />
        </View>
      </SafeAreaView>
    );
  }

  const unreadCount = notifications.filter((n) => !n.read).length;

  return (
    <SafeAreaView style={styles.safe}>
      <View style={styles.headerBar}>
        <Text style={styles.title}>Notificações</Text>
        {unreadCount > 0 && (
          <TouchableOpacity
            style={styles.markAllBtn}
            onPress={handleMarkAll}
            disabled={mutating}
          >
            <Text style={styles.markAllText}>Marcar todas como lidas</Text>
          </TouchableOpacity>
        )}
      </View>

      <View style={styles.filterRow}>
        {FILTERS.map((f) => {
          const active = filter === f.key;
          return (
            <TouchableOpacity
              key={f.key}
              style={[styles.chip, active && styles.chipActive]}
              onPress={() => setFilter(f.key)}
            >
              <Text style={[styles.chipText, active && styles.chipTextActive]}>
                {f.label}
              </Text>
            </TouchableOpacity>
          );
        })}
      </View>

      <FlatList
        data={notifications}
        keyExtractor={(item) => String(item.id)}
        contentContainerStyle={styles.listContent}
        refreshControl={
          <RefreshControl
            refreshing={isLoading}
            onRefresh={refetch}
            colors={[colors.primary]}
          />
        }
        ListEmptyComponent={
          <View style={styles.emptyState}>
            <Text style={styles.emptyIcon}>🔔</Text>
            <Text style={styles.emptyText}>
              {filter === 'unread' ? 'Nenhuma notificação não lida.' : 'Nenhuma notificação.'}
            </Text>
          </View>
        }
        renderItem={({ item }) => (
          <TouchableOpacity
            style={[styles.card, !item.read && styles.cardUnread]}
            onPress={() => handleTap(item)}
            activeOpacity={0.7}
          >
            <View style={styles.cardLeft}>
              {!item.read && <View style={styles.unreadDot} />}
            </View>
            <View style={styles.cardBody}>
              <Text style={[styles.cardTitle, !item.read && styles.cardTitleUnread]} numberOfLines={2}>
                {item.title}
              </Text>
              <Text style={styles.cardBody_text} numberOfLines={3}>
                {item.body}
              </Text>
              <Text style={styles.cardTime}>{formatRelativeDate(item.created_at)}</Text>
            </View>
          </TouchableOpacity>
        )}
      />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.background },
  center: { flex: 1, justifyContent: 'center', alignItems: 'center' },
  headerBar: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: spacing.md,
    paddingTop: spacing.md,
    paddingBottom: spacing.xs,
  },
  title: { fontSize: fontSize.lg, fontWeight: '700', color: colors.text },
  markAllBtn: { paddingVertical: spacing.xs, paddingHorizontal: spacing.sm },
  markAllText: { fontSize: fontSize.sm, color: colors.primary, fontWeight: '600' },
  filterRow: {
    flexDirection: 'row',
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    gap: spacing.sm,
  },
  chip: {
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.xs + 2,
    borderRadius: borderRadius.full,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.surface,
  },
  chipActive: { backgroundColor: colors.primary, borderColor: colors.primary },
  chipText: { fontSize: fontSize.sm, color: colors.text },
  chipTextActive: { color: colors.textInverse, fontWeight: '600' },
  listContent: { paddingHorizontal: spacing.md, paddingBottom: spacing.xxl },
  card: {
    flexDirection: 'row',
    backgroundColor: colors.card,
    borderRadius: borderRadius.md,
    padding: spacing.md,
    marginBottom: spacing.sm,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.05,
    shadowRadius: 3,
    elevation: 1,
  },
  cardUnread: {
    borderLeftWidth: 3,
    borderLeftColor: colors.primary,
  },
  cardLeft: {
    width: 12,
    alignItems: 'center',
    paddingTop: 4,
    marginRight: spacing.sm,
  },
  unreadDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: colors.primary,
  },
  cardBody: { flex: 1 },
  cardTitle: {
    fontSize: fontSize.md,
    color: colors.text,
    marginBottom: 4,
  },
  cardTitleUnread: { fontWeight: '700' },
  cardBody_text: {
    fontSize: fontSize.sm,
    color: colors.textSecondary,
    lineHeight: 20,
    marginBottom: 6,
  },
  cardTime: { fontSize: fontSize.xs, color: colors.textMuted },
  emptyState: { paddingTop: spacing.xxl * 2, alignItems: 'center' },
  emptyIcon: { fontSize: 48, marginBottom: spacing.md },
  emptyText: { fontSize: fontSize.md, color: colors.textSecondary, textAlign: 'center' },
});
