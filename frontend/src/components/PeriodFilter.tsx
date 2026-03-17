import React, { useState } from 'react';
import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
  Switch,
} from 'react-native';
import { colors, spacing, fontSize, borderRadius } from '../theme';
import DateTimePicker from './DateTimePicker';

interface Props {
  onApply: (filters: {
    startDate: Date | null;
    endDate: Date | null;
    exceptionsOnly: boolean;
    countDoneOnly: boolean;
  }) => void;
  onClear: () => void;
}

export default function PeriodFilter({ onApply, onClear }: Props) {
  const [startDate, setStartDate] = useState<Date | null>(null);
  const [endDate, setEndDate] = useState<Date | null>(null);
  const [exceptionsOnly, setExceptionsOnly] = useState(false);
  const [countDoneOnly, setCountDoneOnly] = useState(false);

  const handleApply = () => {
    onApply({
      startDate,
      endDate,
      exceptionsOnly,
      countDoneOnly,
    });
  };

  const handleClear = () => {
    setStartDate(null);
    setEndDate(null);
    setExceptionsOnly(false);
    setCountDoneOnly(false);
    onClear();
  };

  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.title}>Filtrar Período</Text>
        <View style={styles.switches}>
          <View style={styles.switchRow}>
            <Text style={styles.switchLabel}>Só exceções</Text>
            <Switch
              value={exceptionsOnly}
              onValueChange={setExceptionsOnly}
              trackColor={{ false: colors.border, true: colors.primaryLight }}
              thumbColor={exceptionsOnly ? colors.primary : colors.textMuted}
            />
          </View>
          <View style={styles.switchRow}>
            <Text style={styles.switchLabel}>Cards: só realizadas</Text>
            <Switch
              value={countDoneOnly}
              onValueChange={setCountDoneOnly}
              trackColor={{ false: colors.border, true: colors.primaryLight }}
              thumbColor={countDoneOnly ? colors.primary : colors.textMuted}
            />
          </View>
        </View>
      </View>

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

      <View style={styles.actions}>
        <TouchableOpacity style={styles.applyButton} onPress={handleApply}>
          <Text style={styles.applyButtonText}>Aplicar</Text>
        </TouchableOpacity>

        <TouchableOpacity style={styles.clearButton} onPress={handleClear}>
          <Text style={styles.clearButtonText}>✕</Text>
        </TouchableOpacity>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: borderRadius.xl,
    padding: spacing.md,
    marginHorizontal: spacing.md,
    marginBottom: spacing.lg,
  },
  header: {
    marginBottom: spacing.md,
  },
  title: {
    fontSize: fontSize.md,
    fontWeight: '600',
    color: colors.text,
    marginBottom: spacing.sm,
  },
  switches: {
    gap: spacing.xs,
  },
  switchRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  switchLabel: {
    fontSize: fontSize.sm,
    color: colors.textSecondary,
  },
  dateRow: {
    flexDirection: 'row',
    gap: spacing.sm,
    marginBottom: spacing.md,
  },
  dateField: {
    flex: 1,
  },
  actions: {
    flexDirection: 'row',
    gap: spacing.sm,
  },
  applyButton: {
    flex: 1,
    backgroundColor: colors.primary,
    borderRadius: borderRadius.md,
    paddingVertical: spacing.md,
    alignItems: 'center',
    justifyContent: 'center',
  },
  applyButtonText: {
    color: colors.textInverse,
    fontSize: fontSize.md,
    fontWeight: '600',
  },
  clearButton: {
    width: 44,
    height: 44,
    backgroundColor: colors.danger,
    borderRadius: borderRadius.md,
    alignItems: 'center',
    justifyContent: 'center',
  },
  clearButtonText: {
    color: colors.textInverse,
    fontSize: fontSize.xl,
    fontWeight: '600',
  },
});
