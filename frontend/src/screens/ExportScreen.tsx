import React, { useState } from 'react';
import { View, Text, TouchableOpacity, StyleSheet, ScrollView, Alert, Platform } from 'react-native';
import { colors, spacing, fontSize, borderRadius } from '../theme';
import DateTimePicker from '../components/DateTimePicker';
import CategoryCard from '../components/CategoryCard';
import { dashboardApi } from '../api/endpoints';
import { RECORD_TYPES } from '../utils/constants';
import { getLocalDateIso } from '../utils/date';

export default function ExportScreen() {
  const [startDate, setStartDate] = useState<Date | null>(null);
  const [endDate, setEndDate] = useState<Date | null>(null);
  const [selectedCategories, setSelectedCategories] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);

  const toggleCategory = (type: string) => {
    setSelectedCategories((prev) =>
      prev.includes(type) ? prev.filter((t) => t !== type) : [...prev, type]
    );
  };

  const handleExport = async () => {
    const params: Record<string, string> = {};
    if (startDate) params.start = getLocalDateIso(startDate);
    if (endDate) params.end = getLocalDateIso(endDate);
    if (selectedCategories.length > 0) params.categories = selectedCategories.join(',');

    setLoading(true);
    try {
      const response = await dashboardApi.exportCsv(params);

      if (Platform.OS === 'web') {
        const blob = response.data as Blob;
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = 'cuidarjuntos-export.csv';
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        URL.revokeObjectURL(url);
      } else {
        Alert.alert('Exportação concluída', 'O arquivo CSV foi gerado com sucesso.');
      }
    } catch (error) {
      Alert.alert('Erro ao exportar', 'Não foi possível gerar o arquivo CSV. Tente novamente.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <Text style={styles.title}>Exportar Dados</Text>
      <Text style={styles.subtitle}>
        Selecione um intervalo de datas para filtrar a exportação, ou deixe em branco para exportar todos os registros.
      </Text>

      <View style={styles.dateRow}>
        <View style={styles.dateField}>
          <DateTimePicker
            label="Data Inicial"
            value={startDate || new Date()}
            mode="date"
            onChange={setStartDate}
          />
        </View>

        <View style={styles.dateField}>
          <DateTimePicker
            label="Data Final"
            value={endDate || new Date()}
            mode="date"
            onChange={setEndDate}
            minimumDate={startDate || undefined}
          />
        </View>
      </View>

      <Text style={styles.sectionLabel}>Filtrar por categoria</Text>
      <View style={styles.categoryGrid}>
        {RECORD_TYPES.map((type) => (
          <View key={type} style={styles.categoryCardWrapper}>
            <CategoryCard
              type={type}
              selected={selectedCategories.includes(type)}
              hasSelection={selectedCategories.length > 0}
              onPress={() => toggleCategory(type)}
            />
          </View>
        ))}
      </View>

      <TouchableOpacity
        style={[styles.exportButton, loading && styles.exportButtonDisabled]}
        onPress={handleExport}
        disabled={loading}
      >
        <Text style={styles.exportButtonText}>
          {loading ? 'Exportando...' : 'Exportar CSV'}
        </Text>
      </TouchableOpacity>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  content: {
    padding: spacing.md,
  },
  title: {
    fontSize: fontSize.xl,
    fontWeight: '700',
    color: colors.text,
    marginBottom: spacing.xs,
  },
  subtitle: {
    fontSize: fontSize.sm,
    color: colors.textSecondary,
    marginBottom: spacing.lg,
  },
  dateRow: {
    flexDirection: 'row',
    gap: spacing.sm,
    marginBottom: spacing.md,
  },
  dateField: {
    flex: 1,
  },
  sectionLabel: {
    fontSize: fontSize.md,
    fontWeight: '600',
    color: colors.text,
    marginBottom: spacing.sm,
  },
  categoryGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: spacing.sm,
    marginBottom: spacing.lg,
  },
  categoryCardWrapper: {
    width: '31%',
  },
  exportButton: {
    backgroundColor: colors.primary,
    borderRadius: borderRadius.md,
    paddingVertical: spacing.md,
    alignItems: 'center',
    justifyContent: 'center',
  },
  exportButtonDisabled: {
    opacity: 0.6,
  },
  exportButtonText: {
    color: colors.textInverse,
    fontSize: fontSize.md,
    fontWeight: '600',
  },
});
