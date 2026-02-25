import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  ActivityIndicator,
  RefreshControl,
  Dimensions,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { dashboardApi } from '../api/endpoints';
import { colors, spacing, fontSize } from '../theme';
import PeriodFilter from '../components/PeriodFilter';
import CategoryCard from '../components/CategoryCard';
import RecordCard from '../components/RecordCard';
import { RECORD_TYPES } from '../utils/constants';
import type { CareRecord } from '../types/models';

const { width } = Dimensions.get('window');
const isTablet = width >= 768;
const isDesktop = width >= 1024;

export default function DashboardScreen({ navigation }: any) {
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [counts, setCounts] = useState<Record<string, number>>({});
  const [records, setRecords] = useState<CareRecord[]>([]);
  const [selectedCategories, setSelectedCategories] = useState<string[]>([]);
  const [filters, setFilters] = useState({
    startDate: null as Date | null,
    endDate: null as Date | null,
    exceptionsOnly: false,
    countDoneOnly: false,
  });

  const loadData = async () => {
    try {
      const params: any = {};

      if (filters.startDate) {
        const y = filters.startDate.getFullYear();
        const m = String(filters.startDate.getMonth() + 1).padStart(2, '0');
        const d = String(filters.startDate.getDate()).padStart(2, '0');
        params.start = `${y}-${m}-${d}`;
      }

      if (filters.endDate) {
        const y = filters.endDate.getFullYear();
        const m = String(filters.endDate.getMonth() + 1).padStart(2, '0');
        const d = String(filters.endDate.getDate()).padStart(2, '0');
        params.end = `${y}-${m}-${d}`;
      }

      if (filters.exceptionsOnly) params.exceptions = '1';
      if (filters.countDoneOnly) params.count_done_only = '1';
      if (selectedCategories.length > 0) {
        params.categories = selectedCategories.join(',');
      }

      const { data } = await dashboardApi.get(params);
      setCounts(data.counts || {});
      setRecords(data.records || []);
    } catch (error) {
      console.error('Erro ao carregar dashboard:', error);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [filters, selectedCategories]);

  const handleRefresh = () => {
    setRefreshing(true);
    loadData();
  };

  const toggleCategory = (type: string) => {
    setSelectedCategories((prev) =>
      prev.includes(type)
        ? prev.filter((t) => t !== type)
        : [...prev, type]
    );
  };

  const handleClearCategories = () => {
    setSelectedCategories([]);
  };

  if (loading) {
    return (
      <View style={styles.loadingContainer}>
        <ActivityIndicator size="large" color={colors.primary} />
      </View>
    );
  }

  const numColumns = isDesktop ? 3 : isTablet ? 2 : 1;
  const hasSelection = selectedCategories.length > 0;

  return (
    <SafeAreaView style={styles.safe}>
      <ScrollView
        style={styles.scroll}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={handleRefresh} />
        }
      >
        {/* Filtro de Período */}
        <PeriodFilter
          onApply={(newFilters) => setFilters(newFilters)}
          onClear={() =>
            setFilters({
              startDate: null,
              endDate: null,
              exceptionsOnly: false,
              countDoneOnly: false,
            })
          }
        />

        {/* Dica + Link Limpar */}
        <View style={styles.categoryHeader}>
          <Text style={styles.categoryHint}>
            Dica: ative quantos cards quiser para combinar os filtros (clique novamente para limpar).
          </Text>
          {hasSelection && (
            <Text style={styles.clearLink} onPress={handleClearCategories}>
              Ver todas as atividades
            </Text>
          )}
        </View>

        {/* Grid de Cards de Categoria */}
        <View
          style={[
            styles.categoryGrid,
            { gridTemplateColumns: `repeat(${numColumns}, 1fr)` } as any,
          ]}
        >
          {RECORD_TYPES.map((type) => (
            <View
              key={type}
              style={[
                styles.categoryCardWrapper,
                { width: `${100 / numColumns}%` },
              ]}
            >
              <CategoryCard
                type={type}
                count={counts[type] || 0}
                selected={selectedCategories.includes(type)}
                hasSelection={hasSelection}
                onPress={() => toggleCategory(type)}
              />
            </View>
          ))}
        </View>

        {/* Lista de Registros */}
        <View style={styles.recordsSection}>
          {records.length === 0 ? (
            <View style={styles.emptyState}>
              <Text style={styles.emptyText}>
                Nenhum registro encontrado
              </Text>
              <Text style={styles.emptyHint}>
                Ajuste os filtros ou crie um novo registro
              </Text>
            </View>
          ) : (
            records.map((record) => (
              <RecordCard
                key={record.id}
                record={record}
                onPress={() => navigation.navigate('RecordDetail', { id: record.id })}
              />
            ))
          )}
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: {
    flex: 1,
    backgroundColor: colors.background,
  },
  loadingContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: colors.background,
  },
  scroll: {
    flex: 1,
  },
  categoryHeader: {
    paddingHorizontal: spacing.md,
    marginBottom: spacing.sm,
  },
  categoryHint: {
    fontSize: fontSize.xs,
    color: colors.textSecondary,
    marginBottom: spacing.xs,
  },
  clearLink: {
    fontSize: fontSize.xs,
    color: colors.primary,
    fontWeight: '600',
  },
  categoryGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    paddingHorizontal: spacing.md,
    marginBottom: spacing.lg,
  },
  categoryCardWrapper: {
    padding: spacing.xs,
  },
  recordsSection: {
    paddingBottom: spacing.xxl,
  },
  emptyState: {
    padding: spacing.xxl,
    alignItems: 'center',
  },
  emptyText: {
    fontSize: fontSize.lg,
    fontWeight: '600',
    color: colors.textSecondary,
    marginBottom: spacing.xs,
  },
  emptyHint: {
    fontSize: fontSize.sm,
    color: colors.textMuted,
    textAlign: 'center',
  },
});
