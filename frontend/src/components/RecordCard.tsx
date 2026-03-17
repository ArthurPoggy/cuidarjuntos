import React from 'react';
import { View, Text, StyleSheet, TouchableOpacity } from 'react-native';
import { colors, spacing, borderRadius, fontSize } from '../theme';
import { CATEGORY_META } from '../utils/constants';
import StatusBadge from './StatusBadge';
import type { CareRecord } from '../types/models';

interface Props {
  record: CareRecord;
  onPress?: () => void;
}

export default function RecordCard({ record, onPress }: Props) {
  const meta = CATEGORY_META[record.type];

  return (
    <TouchableOpacity
      style={[styles.card, { borderLeftColor: meta?.color || colors.primary }]}
      onPress={onPress}
      activeOpacity={0.7}
    >
      <View style={styles.header}>
        <View style={[styles.typeChip, { backgroundColor: meta?.bg || colors.borderLight }]}>
          <Text style={[styles.typeLabel, { color: meta?.color || colors.text }]}>
            {meta?.label || record.type}
          </Text>
        </View>
        <StatusBadge status={record.status} />
      </View>

      <Text style={styles.what} numberOfLines={2}>
        {record.what || record.description || '-'}
      </Text>

      <View style={styles.footer}>
        <Text style={styles.meta}>
          {record.date} {record.time ? `\u2022 ${record.time}` : ''}
        </Text>
        <Text style={styles.meta} numberOfLines={1}>
          {record.caregiver || record.author_name}
        </Text>
      </View>

      {record.medication_detail ? (
        <Text style={styles.medicationDetail} numberOfLines={1}>
          {record.medication_detail}
        </Text>
      ) : null}
    </TouchableOpacity>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: colors.surface,
    borderRadius: borderRadius.md,
    padding: spacing.md,
    marginHorizontal: spacing.md,
    marginVertical: spacing.xs,
    borderLeftWidth: 4,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.05,
    shadowRadius: 3,
    elevation: 2,
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: spacing.xs,
  },
  typeChip: {
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: borderRadius.sm,
  },
  typeLabel: {
    fontSize: fontSize.xs,
    fontWeight: '600',
  },
  what: {
    fontSize: fontSize.md,
    fontWeight: '500',
    color: colors.text,
    marginBottom: spacing.xs,
  },
  footer: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  meta: {
    fontSize: fontSize.xs,
    color: colors.textSecondary,
  },
  medicationDetail: {
    fontSize: fontSize.xs,
    color: colors.textMuted,
    marginTop: 4,
  },
});
