import React, { useCallback, useEffect, useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ActivityIndicator,
  FlatList,
  ScrollView,
  RefreshControl,
  Dimensions,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { LineChart } from 'react-native-chart-kit';
import { adminApi } from '../api/endpoints';
import { colors, spacing, fontSize, borderRadius } from '../theme';

interface OverviewData {
  total_users: number;
  total_patients: number;
  total_groups: number;
  total_records: number;
  daily_series: { date: string; count: number }[];
  users: { id: number; username: string; email: string; date_joined: string }[];
}

const STAT_CARDS = [
  { key: 'total_users', label: 'Usuarios', color: colors.primary, bg: '#EFF6FF' },
  { key: 'total_patients', label: 'Pacientes', color: colors.success, bg: '#F0FDF4' },
  { key: 'total_groups', label: 'Grupos', color: colors.secondary, bg: '#EEF2FF' },
  { key: 'total_records', label: 'Registros', color: colors.warning, bg: '#FEFCE8' },
];

const screenWidth = Dimensions.get('window').width;

export default function AdminOverviewScreen() {
  const [data, setData] = useState<OverviewData | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState('');

  const fetchOverview = useCallback(async () => {
    try {
      setError('');
      const res = await adminApi.overview();
      setData(res.data as OverviewData);
    } catch {
      setError('Erro ao carregar dados administrativos.');
    }
  }, []);

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      await fetchOverview();
      setLoading(false);
    };
    load();
  }, [fetchOverview]);

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    await fetchOverview();
    setRefreshing(false);
  }, [fetchOverview]);

  if (loading) {
    return (
      <SafeAreaView style={styles.safe}>
        <View style={styles.center}>
          <ActivityIndicator size="large" color={colors.primary} />
        </View>
      </SafeAreaView>
    );
  }

  if (error || !data) {
    return (
      <SafeAreaView style={styles.safe}>
        <View style={styles.center}>
          <Text style={styles.errorText}>{error || 'Erro desconhecido.'}</Text>
        </View>
      </SafeAreaView>
    );
  }

  // Prepare chart data
  const series = data.daily_series ?? [];
  const chartLabels = series.length > 0
    ? series.map((s) => {
        const parts = s.date.split('-');
        return `${parts[2]}/${parts[1]}`;
      })
    : ['--'];
  const chartValues = series.length > 0
    ? series.map((s) => s.count)
    : [0];

  // Reduce labels if too many
  const maxLabels = 7;
  let displayLabels = chartLabels;
  if (displayLabels.length > maxLabels) {
    const step = Math.ceil(displayLabels.length / maxLabels);
    displayLabels = displayLabels.map((label, i) => (i % step === 0 ? label : ''));
  }

  const chartData = {
    labels: displayLabels,
    datasets: [{ data: chartValues }],
  };

  const renderUserItem = ({
    item,
  }: {
    item: { id: number; username: string; email: string; date_joined: string };
  }) => (
    <View style={styles.userRow}>
      <View style={styles.userAvatar}>
        <Text style={styles.userAvatarText}>
          {item.username.charAt(0).toUpperCase()}
        </Text>
      </View>
      <View style={styles.userInfo}>
        <Text style={styles.userUsername}>{item.username}</Text>
        <Text style={styles.userEmail}>{item.email}</Text>
      </View>
      <Text style={styles.userDate}>
        {new Date(item.date_joined).toLocaleDateString('pt-BR')}
      </Text>
    </View>
  );

  return (
    <SafeAreaView style={styles.safe}>
      <FlatList
        data={data.users ?? []}
        keyExtractor={(item) => String(item.id)}
        renderItem={renderUserItem}
        contentContainerStyle={styles.listContent}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} colors={[colors.primary]} />
        }
        ListHeaderComponent={
          <View>
            {/* Stat cards */}
            <View style={styles.statsGrid}>
              {STAT_CARDS.map((stat) => (
                <View key={stat.key} style={[styles.statCard, { backgroundColor: stat.bg }]}>
                  <Text style={[styles.statValue, { color: stat.color }]}>
                    {(data as unknown as Record<string, unknown>)[stat.key] as number ?? 0}
                  </Text>
                  <Text style={[styles.statLabel, { color: stat.color }]}>{stat.label}</Text>
                </View>
              ))}
            </View>

            {/* Chart */}
            {series.length > 0 && (
              <View style={styles.chartContainer}>
                <Text style={styles.chartTitle}>Registros por dia</Text>
                <ScrollView horizontal showsHorizontalScrollIndicator={false}>
                  <LineChart
                    data={chartData}
                    width={Math.max(screenWidth - spacing.md * 2, chartValues.length * 50)}
                    height={220}
                    chartConfig={{
                      backgroundColor: colors.card,
                      backgroundGradientFrom: colors.card,
                      backgroundGradientTo: colors.card,
                      decimalPlaces: 0,
                      color: (opacity = 1) => `rgba(59, 130, 246, ${opacity})`,
                      labelColor: () => colors.textSecondary,
                      propsForDots: {
                        r: '4',
                        strokeWidth: '2',
                        stroke: colors.primary,
                      },
                      propsForBackgroundLines: {
                        stroke: colors.borderLight,
                      },
                    }}
                    bezier
                    style={styles.chart}
                  />
                </ScrollView>
              </View>
            )}

            {/* Users section header */}
            <Text style={styles.sectionTitle}>
              Usuarios ({data.users?.length ?? 0})
            </Text>
          </View>
        }
        ListEmptyComponent={
          <View style={styles.emptyContainer}>
            <Text style={styles.emptyText}>Nenhum usuario encontrado.</Text>
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
  statsGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    justifyContent: 'space-between',
    marginBottom: spacing.md,
  },
  statCard: {
    width: '48%',
    borderRadius: borderRadius.lg,
    padding: spacing.md,
    alignItems: 'center',
    marginBottom: spacing.sm,
  },
  statValue: {
    fontSize: fontSize.xxl,
    fontWeight: '700',
  },
  statLabel: {
    fontSize: fontSize.sm,
    fontWeight: '600',
    marginTop: spacing.xs,
  },
  chartContainer: {
    backgroundColor: colors.card,
    borderRadius: borderRadius.lg,
    padding: spacing.md,
    marginBottom: spacing.lg,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.08,
    shadowRadius: 8,
    elevation: 3,
  },
  chartTitle: {
    fontSize: fontSize.md,
    fontWeight: '600',
    color: colors.text,
    marginBottom: spacing.sm,
  },
  chart: {
    borderRadius: borderRadius.md,
  },
  sectionTitle: {
    fontSize: fontSize.lg,
    fontWeight: '600',
    color: colors.text,
    marginBottom: spacing.sm,
  },
  userRow: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.card,
    borderRadius: borderRadius.md,
    padding: spacing.md,
    marginBottom: spacing.sm,
  },
  userAvatar: {
    width: 38,
    height: 38,
    borderRadius: 19,
    backgroundColor: colors.primary,
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: spacing.sm,
  },
  userAvatarText: {
    color: colors.textInverse,
    fontSize: fontSize.md,
    fontWeight: '700',
  },
  userInfo: {
    flex: 1,
    marginRight: spacing.sm,
  },
  userUsername: {
    fontSize: fontSize.md,
    fontWeight: '500',
    color: colors.text,
  },
  userEmail: {
    fontSize: fontSize.xs,
    color: colors.textSecondary,
    marginTop: 2,
  },
  userDate: {
    fontSize: fontSize.xs,
    color: colors.textMuted,
  },
  emptyContainer: {
    alignItems: 'center',
    paddingVertical: spacing.xxl,
  },
  emptyText: {
    fontSize: fontSize.md,
    color: colors.textSecondary,
  },
  errorText: {
    color: colors.danger,
    fontSize: fontSize.md,
    textAlign: 'center',
  },
});
