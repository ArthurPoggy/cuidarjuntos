import React, { useCallback, useEffect, useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ActivityIndicator,
  FlatList,
  ScrollView,
  TouchableOpacity,
  RefreshControl,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useNavigation } from '@react-navigation/native';
import { dashboardApi } from '../api/endpoints';
import { colors, spacing, fontSize, borderRadius } from '../theme';
import { CATEGORY_META, RECORD_TYPES } from '../utils/constants';
import type { DashboardData, CareRecord } from '../types/models';

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

export default function DashboardScreen() {
  const navigation = useNavigation<any>();
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState('');

  const fetchDashboard = useCallback(async () => {
    try {
      setError('');
      const res = await dashboardApi.get();
      setData(res.data);
    } catch {
      setError('Erro ao carregar o painel. Tente novamente.');
    }
  }, []);

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      await fetchDashboard();
      setLoading(false);
    };
    load();
  }, [fetchDashboard]);

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    await fetchDashboard();
    setRefreshing(false);
  }, [fetchDashboard]);

  const renderCategoryCard = (type: string) => {
    const meta = CATEGORY_META[type];
    if (!meta) return null;
    const count = data?.counts?.[type] ?? 0;
    return (
      <TouchableOpacity
        key={type}
        style={[styles.categoryCard, { backgroundColor: meta.bg }]}
        activeOpacity={0.7}
        onPress={() => navigation.navigate('Records', { filterType: type })}
      >
        <View style={[styles.categoryIconContainer, { backgroundColor: meta.color }]}>
          <Text style={styles.categoryIconText}>{meta.label.charAt(0)}</Text>
        </View>
        <Text style={[styles.categoryLabel, { color: meta.color }]} numberOfLines={1}>
          {meta.label}
        </Text>
        <Text style={[styles.categoryCount, { color: meta.color }]}>{count}</Text>
      </TouchableOpacity>
    );
  };

  const renderRecordCard = ({ item }: { item: CareRecord }) => {
    const meta = CATEGORY_META[item.type];
    const statusColor = STATUS_COLORS[item.status] ?? colors.textMuted;
    const statusLabel = STATUS_LABELS[item.status] ?? item.status;

    return (
      <TouchableOpacity
        style={styles.recordCard}
        activeOpacity={0.7}
        onPress={() => navigation.navigate('RecordDetail', { id: item.id })}
      >
        <View style={styles.recordRow}>
          <View
            style={[
              styles.recordIconContainer,
              { backgroundColor: meta?.bg ?? colors.borderLight },
            ]}
          >
            <Text style={[styles.recordIconText, { color: meta?.color ?? colors.text }]}>
              {meta?.label?.charAt(0) ?? '?'}
            </Text>
          </View>
          <View style={styles.recordInfo}>
            <Text style={styles.recordWhat} numberOfLines={1}>
              {item.what || meta?.label || item.type}
            </Text>
            <Text style={styles.recordMeta}>
              {item.time ? item.time.slice(0, 5) : '--:--'} | {item.author_name || item.caregiver || '---'}
            </Text>
          </View>
          <View style={[styles.statusBadge, { backgroundColor: statusColor }]}>
            <Text style={styles.statusBadgeText}>{statusLabel}</Text>
          </View>
        </View>
      </TouchableOpacity>
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

  if (error) {
    return (
      <SafeAreaView style={styles.safe}>
        <View style={styles.center}>
          <Text style={styles.errorText}>{error}</Text>
          <TouchableOpacity style={styles.retryButton} onPress={onRefresh}>
            <Text style={styles.retryText}>Tentar novamente</Text>
          </TouchableOpacity>
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.safe}>
      <FlatList
        data={data?.records ?? []}
        keyExtractor={(item) => String(item.id)}
        renderItem={renderRecordCard}
        contentContainerStyle={styles.listContent}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} colors={[colors.primary]} />
        }
        ListHeaderComponent={
          <View>
            <Text style={styles.sectionTitle}>Categorias</Text>
            <ScrollView
              horizontal
              showsHorizontalScrollIndicator={false}
              contentContainerStyle={styles.categoriesRow}
            >
              {RECORD_TYPES.map(renderCategoryCard)}
            </ScrollView>
            <Text style={styles.sectionTitle}>Registros recentes</Text>
          </View>
        }
        ListEmptyComponent={
          <View style={styles.emptyContainer}>
            <Text style={styles.emptyText}>Nenhum registro encontrado.</Text>
          </View>
        }
      />

      {/* FAB */}
      <TouchableOpacity
        style={styles.fab}
        activeOpacity={0.85}
        onPress={() => navigation.navigate('RecordCreate')}
      >
        <Text style={styles.fabText}>+</Text>
      </TouchableOpacity>
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
    paddingHorizontal: spacing.md,
    paddingBottom: 80,
  },
  sectionTitle: {
    fontSize: fontSize.lg,
    fontWeight: '600',
    color: colors.text,
    marginTop: spacing.lg,
    marginBottom: spacing.sm,
  },
  categoriesRow: {
    paddingVertical: spacing.sm,
    gap: spacing.sm,
  },
  categoryCard: {
    width: 100,
    borderRadius: borderRadius.md,
    padding: spacing.sm,
    alignItems: 'center',
    marginRight: spacing.sm,
  },
  categoryIconContainer: {
    width: 40,
    height: 40,
    borderRadius: borderRadius.full,
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: spacing.xs,
  },
  categoryIconText: {
    color: colors.textInverse,
    fontSize: fontSize.lg,
    fontWeight: '700',
  },
  categoryLabel: {
    fontSize: fontSize.xs,
    fontWeight: '600',
    textAlign: 'center',
    marginBottom: 2,
  },
  categoryCount: {
    fontSize: fontSize.lg,
    fontWeight: '700',
  },
  recordCard: {
    backgroundColor: colors.card,
    borderRadius: borderRadius.md,
    padding: spacing.md,
    marginBottom: spacing.sm,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.06,
    shadowRadius: 4,
    elevation: 2,
  },
  recordRow: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  recordIconContainer: {
    width: 42,
    height: 42,
    borderRadius: borderRadius.full,
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: spacing.sm,
  },
  recordIconText: {
    fontSize: fontSize.lg,
    fontWeight: '700',
  },
  recordInfo: {
    flex: 1,
    marginRight: spacing.sm,
  },
  recordWhat: {
    fontSize: fontSize.md,
    fontWeight: '500',
    color: colors.text,
  },
  recordMeta: {
    fontSize: fontSize.xs,
    color: colors.textSecondary,
    marginTop: 2,
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
  emptyContainer: {
    alignItems: 'center',
    paddingVertical: spacing.xxl,
  },
  emptyText: {
    fontSize: fontSize.md,
    color: colors.textSecondary,
  },
  fab: {
    position: 'absolute',
    right: spacing.lg,
    bottom: spacing.lg,
    width: 58,
    height: 58,
    borderRadius: 29,
    backgroundColor: colors.primary,
    justifyContent: 'center',
    alignItems: 'center',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.2,
    shadowRadius: 8,
    elevation: 6,
  },
  fabText: {
    color: colors.textInverse,
    fontSize: fontSize.xxl,
    fontWeight: '400',
    marginTop: -2,
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
