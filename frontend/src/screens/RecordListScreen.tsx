import React, { useCallback, useEffect, useRef, useState } from 'react';
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
import RecordCard from '../components/RecordCard';
import DateTimePicker from '../components/DateTimePicker';
import type { CareRecord } from '../types/models';

interface RecordAuthor {
  id: number;
  name: string;
}

const toISODate = (date: Date) => {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, '0');
  const d = String(date.getDate()).padStart(2, '0');
  return `${y}-${m}-${d}`;
};

export default function RecordListScreen() {
  const navigation = useNavigation<any>();
  const route = useRoute<any>();
  const initialFilter = route.params?.filterType ?? '';

  const [records, setRecords] = useState<CareRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [filtering, setFiltering] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState('');
  const [activeFilter, setActiveFilter] = useState(initialFilter);
  const [dateFrom, setDateFrom] = useState<Date | null>(null);
  const [dateTo, setDateTo] = useState<Date | null>(null);
  const [authorFilter, setAuthorFilter] = useState('');
  const [showFilters, setShowFilters] = useState(false);
  const [authors, setAuthors] = useState<RecordAuthor[]>([]);
  const [nextPage, setNextPage] = useState<string | null>(null);
  const [page, setPage] = useState(1);

  const isMountedRef = useRef(true);
  const isFirstLoadRef = useRef(true);
  const requestIdRef = useRef(0);
  const filterEffectIdRef = useRef(0);

  useEffect(
    () => () => {
      isMountedRef.current = false;
    },
    [],
  );

  const activeFilterCount =
    (activeFilter ? 1 : 0) + (authorFilter ? 1 : 0) + (dateFrom || dateTo ? 1 : 0);
  const hasActiveFilters = activeFilterCount > 0;

  useEffect(() => {
    let cancelled = false;
    recordsApi
      .authors()
      .then((res) => {
        if (!cancelled && isMountedRef.current) setAuthors(res.data);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, []);

  const buildParams = useCallback(
    (pageNum: number) => {
      const params: Record<string, string> = { page: String(pageNum) };
      if (activeFilter) params.type = activeFilter;
      if (dateFrom) params.date_from = toISODate(dateFrom);
      if (dateTo) params.date_to = toISODate(dateTo);
      if (authorFilter) params.author = authorFilter;
      return params;
    },
    [activeFilter, dateFrom, dateTo, authorFilter],
  );

  const fetchRecords = useCallback(
    async (pageNum: number, append = false) => {
      const requestId = ++requestIdRef.current;
      if (!isMountedRef.current) return;
      // setError('') so nao roda se ja estava vazio: evita uma escrita de
      // estado descartavel a cada requisicao (inclusive requisicoes que serao
      // superadas por uma mais recente antes de resolver), reduzindo o
      // volume de setState assincronos concorrentes durante trocas rapidas
      // de filtro.
      setError((prev) => (prev ? '' : prev));
      try {
        const res = await recordsApi.list(buildParams(pageNum));
        if (!isMountedRef.current || requestId !== requestIdRef.current) return;
        if (append) {
          setRecords((prev) => [...prev, ...res.data.results]);
        } else {
          setRecords(res.data.results);
        }
        setNextPage(res.data.next);
      } catch {
        if (!isMountedRef.current || requestId !== requestIdRef.current) return;
        setError('Erro ao carregar registros.');
      }
    },
    [buildParams],
  );

  // Re-busca a lista sempre que um filtro (tipo, intervalo de datas ou autor)
  // muda, garantindo atualizacao imediata. Apenas o primeiro carregamento usa
  // o spinner de tela cheia; trocas de filtro mantem o painel visivel e usam
  // um indicador de carregamento inline, para nao "sumir" com os controles.
  // filterEffectIdRef marca qual execucao deste efeito e a mais recente: como
  // mudancas rapidas e sucessivas de filtro (ex.: tipo -> autor -> limpar)
  // disparam varias execucoes assincronas em paralelo, sem essa guarda uma
  // execucao antiga poderia resolver depois da mais nova e sobrescrever
  // setLoading/setFiltering com um valor desatualizado, deixando a indicacao
  // visual de filtros ativos temporariamente inconsistente com o estado real.
  useEffect(() => {
    const effectId = ++filterEffectIdRef.current;
    const load = async () => {
      if (!isMountedRef.current || effectId !== filterEffectIdRef.current) return;
      setPage(1);
      if (isFirstLoadRef.current) {
        setLoading(true);
      } else {
        setFiltering(true);
      }
      await fetchRecords(1);
      if (!isMountedRef.current || effectId !== filterEffectIdRef.current) return;
      setLoading(false);
      setFiltering(false);
      isFirstLoadRef.current = false;
    };
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeFilter, dateFrom, dateTo, authorFilter, fetchRecords]);

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    setPage(1);
    await fetchRecords(1);
    if (isMountedRef.current) setRefreshing(false);
  }, [fetchRecords]);

  const onEndReached = useCallback(async () => {
    if (!nextPage || loadingMore) return;
    setLoadingMore(true);
    const nextPageNum = page + 1;
    setPage(nextPageNum);
    await fetchRecords(nextPageNum, true);
    if (isMountedRef.current) setLoadingMore(false);
  }, [nextPage, loadingMore, page, fetchRecords]);

  const handleFilterPress = (type: string) => {
    setActiveFilter((prev: string) => (prev === type ? '' : type));
  };

  const handleAuthorPress = (id: number) => {
    setAuthorFilter((prev) => (prev === String(id) ? '' : String(id)));
  };

  const handleClearFilters = () => {
    setActiveFilter('');
    setDateFrom(null);
    setDateTo(null);
    setAuthorFilter('');
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

  const renderAuthorChip = (author: RecordAuthor) => {
    const isActive = authorFilter === String(author.id);
    return (
      <TouchableOpacity
        key={author.id}
        style={[
          styles.chip,
          styles.authorChip,
          isActive
            ? { backgroundColor: colors.primary }
            : { backgroundColor: colors.borderLight, borderColor: colors.border, borderWidth: 1 },
        ]}
        activeOpacity={0.7}
        onPress={() => handleAuthorPress(author.id)}
      >
        <Text style={[styles.chipText, { color: isActive ? colors.textInverse : colors.text }]}>
          {author.name}
        </Text>
      </TouchableOpacity>
    );
  };

  const renderItem = ({ item }: { item: CareRecord }) => (
    <RecordCard
      record={item}
      onPress={() => navigation.navigate('RecordDetail', { id: item.id })}
    />
  );

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
      {/* Renderizada fora do ListHeaderComponent de proposito: o FlatList e a
          VirtualizedList que ele encapsula tem seu proprio ciclo de vida
          (shouldComponentUpdate/getDerivedStateFromProps) que pode adiar a
          atualizacao do cabecalho quando varias mudancas de estado chegam em
          sequencia rapida (ex.: aplicar tipo, depois autor, depois "Limpar
          filtros", como o fluxo de filtros combinaveis permite). Deixando os
          controles de filtro como irmaos do FlatList, eles re-renderizam no
          mesmo commit do restante da tela, sem depender do agendamento
          interno da lista - o que evita a indicacao visual de filtros ativos
          ficar temporariamente dessincronizada do estado real. */}
      <View>
        <ScrollView
          horizontal
          showsHorizontalScrollIndicator={false}
          contentContainerStyle={styles.chipRow}
        >
          {RECORD_TYPES.map(renderFilterChip)}
        </ScrollView>

        <View style={styles.filterBar}>
          <TouchableOpacity
            style={[styles.filterToggle, hasActiveFilters && styles.filterToggleActive]}
            activeOpacity={0.7}
            onPress={() => setShowFilters((prev) => !prev)}
          >
            <Text
              style={[
                styles.filterToggleText,
                hasActiveFilters && styles.filterToggleTextActive,
              ]}
            >
              Filtros{hasActiveFilters ? ` (${activeFilterCount})` : ''}
            </Text>
          </TouchableOpacity>

          {filtering && (
            <ActivityIndicator size="small" color={colors.primary} testID="filtering-indicator" />
          )}

          {hasActiveFilters && (
            <View style={styles.activeFiltersInfo}>
              <Text style={styles.activeFiltersText}>
                {activeFilterCount} {activeFilterCount === 1 ? 'filtro ativo' : 'filtros ativos'}
              </Text>
              <TouchableOpacity onPress={handleClearFilters} activeOpacity={0.7}>
                <Text style={styles.clearFiltersText}>Limpar filtros</Text>
              </TouchableOpacity>
            </View>
          )}
        </View>

        {showFilters && (
          <View style={styles.filterPanel}>
            <View style={styles.dateRow}>
              <View style={styles.dateField}>
                <DateTimePicker
                  label="Data Inicial"
                  value={dateFrom || new Date()}
                  mode="date"
                  onChange={setDateFrom}
                  maximumDate={dateTo || undefined}
                />
              </View>
              <View style={styles.dateField}>
                <DateTimePicker
                  label="Data Final"
                  value={dateTo || new Date()}
                  mode="date"
                  onChange={setDateTo}
                  minimumDate={dateFrom || undefined}
                />
              </View>
            </View>

            <Text style={styles.filterPanelLabel}>Autor / Responsável</Text>
            <ScrollView
              horizontal
              showsHorizontalScrollIndicator={false}
              contentContainerStyle={styles.chipRow}
            >
              {authors.map(renderAuthorChip)}
            </ScrollView>
          </View>
        )}
      </View>
      <FlatList
        style={styles.list}
        data={records}
        keyExtractor={(item) => String(item.id)}
        renderItem={renderItem}
        contentContainerStyle={styles.listContent}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} colors={[colors.primary]} />
        }
        onEndReached={onEndReached}
        onEndReachedThreshold={0.4}
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
  list: {
    flex: 1,
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
  authorChip: {
    marginRight: spacing.sm,
  },
  chipText: {
    fontSize: fontSize.xs,
    fontWeight: '600',
  },
  filterBar: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingBottom: spacing.sm,
    flexWrap: 'wrap',
    gap: spacing.sm,
  },
  filterToggle: {
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.xs + 2,
    borderRadius: borderRadius.md,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.surface,
  },
  filterToggleActive: {
    borderColor: colors.primary,
    backgroundColor: colors.primaryLight + '22',
  },
  filterToggleText: {
    fontSize: fontSize.sm,
    fontWeight: '600',
    color: colors.text,
  },
  filterToggleTextActive: {
    color: colors.primary,
  },
  activeFiltersInfo: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
  },
  activeFiltersText: {
    fontSize: fontSize.xs,
    color: colors.textSecondary,
  },
  clearFiltersText: {
    fontSize: fontSize.xs,
    fontWeight: '600',
    color: colors.danger,
  },
  filterPanel: {
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: borderRadius.lg,
    padding: spacing.md,
    marginBottom: spacing.md,
  },
  dateRow: {
    flexDirection: 'row',
    gap: spacing.sm,
  },
  dateField: {
    flex: 1,
  },
  filterPanelLabel: {
    fontSize: fontSize.sm,
    fontWeight: '600',
    color: colors.text,
    marginTop: spacing.xs,
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
