import React, { useCallback, useEffect, useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ActivityIndicator,
  FlatList,
  TouchableOpacity,
  TextInput,
  RefreshControl,
  Alert,
  ScrollView,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { dashboardApi, recordsApi } from '../api/endpoints';
import { colors, spacing, fontSize, borderRadius } from '../theme';
import { CATEGORY_META, RECORD_TYPES } from '../utils/constants';
import type { UpcomingBucket, BucketItem } from '../types/models';

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

type ListEntry =
  | { kind: 'header'; key: string; dateIso: string; dayLabel: string }
  | { kind: 'item'; key: string; item: BucketItem; dateIso: string };

export default function UpcomingScreen() {
  const [buckets, setBuckets] = useState<UpcomingBucket[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState('');
  const [activeFilter, setActiveFilter] = useState('');
  const [search, setSearch] = useState('');
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());

  const fetchBuckets = useCallback(async () => {
    try {
      setError('');
      const params: Record<string, string> = {};
      if (activeFilter) params.type = activeFilter;
      if (search.trim()) params.search = search.trim();
      const res = await dashboardApi.upcomingBuckets(params);
      setBuckets(res.data.buckets);
    } catch {
      setError('Erro ao carregar agenda.');
    }
  }, [activeFilter, search]);

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      await fetchBuckets();
      setLoading(false);
    };
    load();
  }, [fetchBuckets]);

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    await fetchBuckets();
    setRefreshing(false);
  }, [fetchBuckets]);

  const toggleSelect = (id: number) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const handleBulkAction = async (status: 'done' | 'missed') => {
    const ids = Array.from(selectedIds);
    if (ids.length === 0) return;

    const label = status === 'done' ? 'feito' : 'perdido';
    Alert.alert(
      'Confirmar acao',
      `Marcar ${ids.length} item(ns) como ${label}?`,
      [
        { text: 'Cancelar', style: 'cancel' },
        {
          text: 'Confirmar',
          onPress: async () => {
            try {
              await recordsApi.bulkSetStatus({ ids, status });
              setSelectedIds(new Set());
              await fetchBuckets();
            } catch {
              Alert.alert('Erro', 'Nao foi possivel atualizar os registros.');
            }
          },
        },
      ],
    );
  };

  const formatDayLabel = (dateIso: string): string => {
    const today = new Date();
    const d = new Date(dateIso + 'T00:00:00');
    const todayStr = today.toISOString().slice(0, 10);
    const tomorrowDate = new Date(today);
    tomorrowDate.setDate(tomorrowDate.getDate() + 1);
    const tomorrowStr = tomorrowDate.toISOString().slice(0, 10);

    if (dateIso === todayStr) return 'Hoje';
    if (dateIso === tomorrowStr) return 'Amanha';

    const weekdays = ['Domingo', 'Segunda', 'Terca', 'Quarta', 'Quinta', 'Sexta', 'Sabado'];
    const dayOfWeek = weekdays[d.getDay()];
    const day = String(d.getDate()).padStart(2, '0');
    const month = String(d.getMonth() + 1).padStart(2, '0');
    return `${dayOfWeek}, ${day}/${month}`;
  };

  // Build flat list data
  const flatData: ListEntry[] = [];
  for (const bucket of buckets) {
    flatData.push({
      kind: 'header',
      key: `header-${bucket.date_iso}`,
      dateIso: bucket.date_iso,
      dayLabel: formatDayLabel(bucket.date_iso),
    });
    for (const item of bucket.items) {
      flatData.push({
        kind: 'item',
        key: `item-${bucket.date_iso}-${item.id}`,
        item,
        dateIso: bucket.date_iso,
      });
    }
  }

  const renderEntry = ({ item: entry }: { item: ListEntry }) => {
    if (entry.kind === 'header') {
      return (
        <View style={styles.dayHeader}>
          <Text style={styles.dayHeaderText}>{entry.dayLabel}</Text>
        </View>
      );
    }

    const { item } = entry;
    const meta = CATEGORY_META[item.type];
    const statusColor = STATUS_COLORS[item.status] ?? colors.textMuted;
    const statusLabel = STATUS_LABELS[item.status] ?? item.status;
    const isSelected = selectedIds.has(item.id);

    return (
      <TouchableOpacity
        style={[styles.itemCard, isSelected && styles.itemCardSelected]}
        activeOpacity={0.7}
        onPress={() => toggleSelect(item.id)}
      >
        {/* Checkbox */}
        <View style={[styles.checkbox, isSelected && styles.checkboxChecked]}>
          {isSelected && <Text style={styles.checkmark}>{'✓'}</Text>}
        </View>

        <View
          style={[
            styles.itemIcon,
            { backgroundColor: meta?.bg ?? colors.borderLight },
          ]}
        >
          <Text style={[styles.itemIconText, { color: meta?.color ?? colors.text }]}>
            {meta?.label?.charAt(0) ?? '?'}
          </Text>
        </View>

        <View style={styles.itemInfo}>
          <Text style={styles.itemTitle} numberOfLines={1}>
            {item.title}
          </Text>
          <Text style={styles.itemTime}>
            {item.time ? item.time.slice(0, 5) : '--:--'} | {item.who || '---'}
          </Text>
        </View>

        <View style={[styles.statusBadge, { backgroundColor: statusColor }]}>
          <Text style={styles.statusBadgeText}>{statusLabel}</Text>
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
      {/* Search bar */}
      <View style={styles.searchContainer}>
        <TextInput
          style={styles.searchInput}
          placeholder="Buscar..."
          placeholderTextColor={colors.textMuted}
          value={search}
          onChangeText={setSearch}
          returnKeyType="search"
        />
      </View>

      {/* Filter chips */}
      <ScrollView
        horizontal
        showsHorizontalScrollIndicator={false}
        contentContainerStyle={styles.chipRow}
      >
        {RECORD_TYPES.map((type) => {
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
              onPress={() => setActiveFilter((prev) => (prev === type ? '' : type))}
            >
              <Text
                style={[styles.chipText, { color: isActive ? colors.textInverse : meta.color }]}
              >
                {meta.label}
              </Text>
            </TouchableOpacity>
          );
        })}
      </ScrollView>

      {/* Bulk actions */}
      {selectedIds.size > 0 && (
        <View style={styles.bulkBar}>
          <Text style={styles.bulkBarText}>{selectedIds.size} selecionado(s)</Text>
          <TouchableOpacity
            style={[styles.bulkBtn, { backgroundColor: colors.success }]}
            onPress={() => handleBulkAction('done')}
          >
            <Text style={styles.bulkBtnText}>Feito</Text>
          </TouchableOpacity>
          <TouchableOpacity
            style={[styles.bulkBtn, { backgroundColor: colors.danger }]}
            onPress={() => handleBulkAction('missed')}
          >
            <Text style={styles.bulkBtnText}>Perdido</Text>
          </TouchableOpacity>
          <TouchableOpacity
            style={[styles.bulkBtn, { backgroundColor: colors.textMuted }]}
            onPress={() => setSelectedIds(new Set())}
          >
            <Text style={styles.bulkBtnText}>Limpar</Text>
          </TouchableOpacity>
        </View>
      )}

      <FlatList
        data={flatData}
        keyExtractor={(entry) => entry.key}
        renderItem={renderEntry}
        contentContainerStyle={styles.listContent}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} colors={[colors.primary]} />
        }
        ListEmptyComponent={
          <View style={styles.emptyContainer}>
            <Text style={styles.emptyText}>
              {error || 'Nenhum evento futuro encontrado.'}
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
  searchContainer: {
    paddingHorizontal: spacing.md,
    paddingTop: spacing.md,
  },
  searchInput: {
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: borderRadius.md,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    fontSize: fontSize.sm,
    color: colors.text,
  },
  chipRow: {
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
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
  bulkBar: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.card,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    borderTopWidth: 1,
    borderBottomWidth: 1,
    borderColor: colors.border,
    gap: spacing.sm,
  },
  bulkBarText: {
    flex: 1,
    fontSize: fontSize.sm,
    fontWeight: '600',
    color: colors.text,
  },
  bulkBtn: {
    paddingHorizontal: spacing.sm,
    paddingVertical: spacing.xs + 2,
    borderRadius: borderRadius.md,
  },
  bulkBtnText: {
    color: colors.textInverse,
    fontSize: fontSize.xs,
    fontWeight: '600',
  },
  listContent: {
    paddingHorizontal: spacing.md,
    paddingBottom: spacing.lg,
  },
  dayHeader: {
    paddingVertical: spacing.sm,
    marginTop: spacing.md,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
    marginBottom: spacing.xs,
  },
  dayHeaderText: {
    fontSize: fontSize.md,
    fontWeight: '700',
    color: colors.text,
  },
  itemCard: {
    flexDirection: 'row',
    alignItems: 'center',
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
  itemCardSelected: {
    borderWidth: 1,
    borderColor: colors.primary,
    backgroundColor: '#F0F7FF',
  },
  checkbox: {
    width: 22,
    height: 22,
    borderRadius: 4,
    borderWidth: 2,
    borderColor: colors.border,
    marginRight: spacing.sm,
    justifyContent: 'center',
    alignItems: 'center',
  },
  checkboxChecked: {
    backgroundColor: colors.primary,
    borderColor: colors.primary,
  },
  checkmark: {
    color: colors.textInverse,
    fontSize: 14,
    fontWeight: '700',
  },
  itemIcon: {
    width: 36,
    height: 36,
    borderRadius: 18,
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: spacing.sm,
  },
  itemIconText: {
    fontSize: fontSize.md,
    fontWeight: '700',
  },
  itemInfo: {
    flex: 1,
    marginRight: spacing.sm,
  },
  itemTitle: {
    fontSize: fontSize.sm,
    fontWeight: '500',
    color: colors.text,
  },
  itemTime: {
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
