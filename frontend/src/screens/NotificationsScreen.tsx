import React, { useCallback, useEffect, useRef, useState } from 'react';
import {
  View, Text, StyleSheet, FlatList, TouchableOpacity,
  ActivityIndicator, RefreshControl,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { notificationsApi } from '../api/endpoints';
import { refreshUnreadNotifications } from '../hooks/useUnreadNotifications';
import type { Notification } from '../types/models';
import { colors, spacing, fontSize, borderRadius } from '../theme';

const FILTERS = [
  { key: 'all', label: 'Todas' },
  { key: 'unread', label: 'Não lidas' },
] as const;

type Filter = typeof FILTERS[number]['key'];

function errorMessage(err: any): string {
  return err?.response?.data?.detail || err?.message || 'Erro ao carregar notificações.';
}

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
  const [items, setItems] = useState<Notification[]>([]);
  const [page, setPage] = useState(1);
  const [hasNext, setHasNext] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [mutating, setMutating] = useState(false);

  /**
   * Identifica a requisição mais recente. Sem isso, uma resposta lenta de um
   * filtro anterior chegaria depois e sobrescreveria a lista do filtro atual
   * (ex.: tocar "Não lidas" e voltar para "Todas" antes da primeira responder).
   */
  const requestId = useRef(0);

  /**
   * Carrega uma página. `append` acumula (scroll infinito); caso contrário
   * substitui a lista. Erros ficam visíveis na UI em vez de silenciosos.
   */
  const fetchPage = useCallback(
    async (targetPage: number, mode: 'replace' | 'append') => {
      const currentRequest = ++requestId.current;
      try {
        const { data } = await notificationsApi.list({
          unread: filter === 'unread' ? true : undefined,
          page: targetPage,
        });
        // Chegou tarde: já existe uma busca mais nova em andamento. Descarta.
        if (currentRequest !== requestId.current) return;
        setItems((prev) => (mode === 'append' ? [...prev, ...data.results] : data.results));
        setHasNext(Boolean(data.next));
        setPage(targetPage);
        setError(null);
      } catch (err) {
        // Idem para o erro: não mostra falha de uma busca que já foi superada.
        if (currentRequest !== requestId.current) return;
        setError(errorMessage(err));
      }
    },
    [filter]
  );

  // Recarrega do zero sempre que o filtro muda.
  useEffect(() => {
    let active = true;
    setIsLoading(true);
    fetchPage(1, 'replace').finally(() => {
      if (active) setIsLoading(false);
    });
    return () => {
      active = false;
    };
  }, [fetchPage]);

  const handleRefresh = useCallback(async () => {
    setIsRefreshing(true);
    await fetchPage(1, 'replace');
    setIsRefreshing(false);
  }, [fetchPage]);

  const handleRetry = useCallback(async () => {
    setIsLoading(true);
    await fetchPage(1, 'replace');
    setIsLoading(false);
  }, [fetchPage]);

  const handleLoadMore = useCallback(async () => {
    if (!hasNext || isLoadingMore || isLoading || isRefreshing) return;
    setIsLoadingMore(true);
    await fetchPage(page + 1, 'append');
    setIsLoadingMore(false);
  }, [fetchPage, hasNext, isLoading, isLoadingMore, isRefreshing, page]);

  const handleTap = useCallback(
    async (item: Notification) => {
      if (item.read) return;
      const previous = items;
      // Atualização otimista: a linha muda na hora e o badge do Header também.
      setItems((prev) =>
        filter === 'unread'
          ? prev.filter((n) => n.id !== item.id)
          : prev.map((n) => (n.id === item.id ? { ...n, read: true } : n))
      );
      try {
        await notificationsApi.markRead(item.id);
        refreshUnreadNotifications();
      } catch (err) {
        setItems(previous);
        setError(errorMessage(err));
      }
    },
    [filter, items]
  );

  const handleMarkAll = useCallback(async () => {
    setMutating(true);
    const previous = items;
    setItems((prev) => (filter === 'unread' ? [] : prev.map((n) => ({ ...n, read: true }))));
    try {
      await notificationsApi.markAllRead();
      refreshUnreadNotifications();
      setError(null);
    } catch (err) {
      setItems(previous);
      setError(errorMessage(err));
    } finally {
      setMutating(false);
    }
  }, [filter, items]);

  if (isLoading) {
    return (
      <SafeAreaView style={styles.safe}>
        <View style={styles.center}>
          <ActivityIndicator size="large" color={colors.primary} />
        </View>
      </SafeAreaView>
    );
  }

  // Erro sem nada carregado: tela inteira de erro com ação de tentar de novo.
  if (error && items.length === 0) {
    return (
      <SafeAreaView style={styles.safe}>
        <View style={styles.center}>
          <Text style={styles.errorIcon}>⚠️</Text>
          <Text style={styles.errorText}>{error}</Text>
          <TouchableOpacity style={styles.retryButton} onPress={handleRetry} activeOpacity={0.7}>
            <Text style={styles.retryButtonText}>Tentar novamente</Text>
          </TouchableOpacity>
        </View>
      </SafeAreaView>
    );
  }

  const unreadCount = items.filter((n) => !n.read).length;

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

      {/* Erro com lista já carregada: faixa discreta, sem descartar o conteúdo. */}
      {error && (
        <TouchableOpacity style={styles.errorBanner} onPress={handleRetry} activeOpacity={0.7}>
          <Text style={styles.errorBannerText}>{error} Toque para tentar de novo.</Text>
        </TouchableOpacity>
      )}

      <FlatList
        data={items}
        keyExtractor={(item) => String(item.id)}
        contentContainerStyle={styles.listContent}
        refreshControl={
          <RefreshControl
            refreshing={isRefreshing}
            onRefresh={handleRefresh}
            colors={[colors.primary]}
          />
        }
        onEndReached={handleLoadMore}
        onEndReachedThreshold={0.4}
        ListFooterComponent={
          isLoadingMore ? (
            <View style={styles.footer}>
              <ActivityIndicator size="small" color={colors.primary} />
            </View>
          ) : null
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
  center: { flex: 1, justifyContent: 'center', alignItems: 'center', padding: spacing.lg },
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
  errorIcon: { fontSize: 40, marginBottom: spacing.sm },
  errorText: {
    fontSize: fontSize.md,
    color: colors.text,
    textAlign: 'center',
    marginBottom: spacing.md,
  },
  retryButton: {
    backgroundColor: colors.primary,
    borderRadius: borderRadius.lg,
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.sm,
  },
  retryButtonText: { color: colors.textInverse, fontWeight: '600', fontSize: fontSize.md },
  errorBanner: {
    marginHorizontal: spacing.md,
    marginBottom: spacing.sm,
    padding: spacing.sm,
    borderRadius: borderRadius.md,
    borderWidth: 1,
    borderColor: colors.danger,
    backgroundColor: colors.surface,
  },
  errorBannerText: { fontSize: fontSize.sm, color: colors.danger },
  footer: { paddingVertical: spacing.md, alignItems: 'center' },
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
