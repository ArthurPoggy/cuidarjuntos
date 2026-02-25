import React, { useCallback, useEffect, useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ActivityIndicator,
  FlatList,
  TouchableOpacity,
  RefreshControl,
  ScrollView,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useNavigation, useRoute } from '@react-navigation/native';
import { recordsApi } from '../api/endpoints';
import { colors, spacing, fontSize, borderRadius } from '../theme';
import { CATEGORY_META, RECORD_TYPES } from '../utils/constants';
import type { CareRecord } from '../types/models';

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

export default function RecordListScreen() {
  const navigation = useNavigation<any>();
  const route = useRoute<any>();
  const initialFilter = route.params?.filterType ?? '';

  const [records, setRecords] = useState<CareRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState('');
  const [activeFilter, setActiveFilter] = useState(initialFilter);
  const [nextPage, setNextPage] = useState<string | null>(null);
  const [page, setPage] = useState(1);

  const fetchRecords = useCallback(
    async (pageNum: number, filter: string, append = false) => {
      try {
        setError('');
        const params: Record<string, string> = { page: String(pageNum) };
        if (filter) params.type = filter;
        const res = await recordsApi.list(params);
        if (append) {
          setRecords((prev) => [...prev, ...res.data.results]);
        } else {
          setRecords(res.data.results);
        }
        setNextPage(res.data.next);
      } catch {
        setError('Erro ao carregar registros.');
      }
    },
    [],
  );

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      setPage(1);
      await fetchRecords(1, activeFilter);
      setLoading(false);
    };
    load();
  }, [activeFilter, fetchRecords]);

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    setPage(1);
    await fetchRecords(1, activeFilter);
    setRefreshing(false);
  }, [activeFilter, fetchRecords]);

  const onEndReached = useCallback(async () => {
    if (!nextPage || loadingMore) return;
    setLoadingMore(true);
    const nextPageNum = page + 1;
    setPage(nextPageNum);
    await fetchRecords(nextPageNum, activeFilter, true);
    setLoadingMore(false);
  }, [nextPage, loadingMore, page, activeFilter, fetchRecords]);

  const handleFilterPress = (type: string) => {
    setActiveFilter((prev: string) => (prev === type ? '' : type));
  };

  const renderFilterChip = (type: string) => {
    const meta = CATEGORY_META[type];
    if (!meta) return null;
    const isActive = activeFilter === type;
    return (
      <TouchableOpacity
        key={type}
        style={[
          styles.chip,
          isActive && { backgroundColor: meta.color },
          !isActive && { backgroundColor: meta.bg, borderColor: meta.color, borderWidth: 1 },
        ]}
        activeOpacity={0.7}
        onPress={() => handleFilterPress(type)}
      >
        <Text style={[styles.chipText, { color: isActive ? colors.textInverse : meta.color }]}>
          {meta.label}
        </Text>
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
            <Text style={styles.recordDate}>
              {item.date} | {item.time ? item.time.slice(0, 5) : '--:--'}
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

  return (
    <SafeAreaView style={styles.safe}>
      <FlatList
        data={records}
        keyExtractor={(item) => String(item.id)}
        renderItem={renderRecordCard}
        contentContainerStyle={styles.listContent}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} colors={[colors.primary]} />
        }
        onEndReached={onEndReached}
        onEndReachedThreshold={0.4}
        ListHeaderComponent={
          <ScrollView
            horizontal
            showsHorizontalScrollIndicator={false}
            contentContainerStyle={styles.chipRow}
          >
            {RECORD_TYPES.map(renderFilterChip)}
          </ScrollView>
        }
        ListFooterComponent={
          loadingMore ? (
            <ActivityIndicator
              size="small"
              color={colors.primary}
              style={{ marginVertical: spacing.md }}
            />
          ) : null
        }
        ListEmptyComponent={
          <View style={styles.emptyContainer}>
            <Text style={styles.emptyText}>
              {error || 'Nenhum registro encontrado.'}
            </Text>
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
  },
  listContent: {
    paddingHorizontal: spacing.md,
    paddingBottom: spacing.lg,
  },
  chipRow: {
    paddingVertical: spacing.md,
    gap: spacing.sm,
  },
  chip: {
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.xs + 2,
    borderRadius: borderRadius.full,
    marginRight: spacing.sm,
  },
  chipText: {
    fontSize: fontSize.xs,
    fontWeight: '600',
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
  recordDate: {
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
});
