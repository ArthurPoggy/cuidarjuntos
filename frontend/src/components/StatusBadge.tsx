import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { colors, borderRadius, fontSize } from '../theme';
import { RecordStatus } from '../types/models';

const STATUS_CONFIG: Record<string, { label: string; color: string; bg: string }> = {
  [RecordStatus.PENDING]: { label: 'Pendente', color: colors.statusPending, bg: '#FEF3C7' },
  [RecordStatus.DONE]: { label: 'Realizada', color: colors.statusDone, bg: '#D1FAE5' },
  [RecordStatus.MISSED]: { label: 'Nao realizado', color: colors.statusMissed, bg: '#FEE2E2' },
};

interface Props {
  status: string;
}

export default function StatusBadge({ status }: Props) {
  const config = STATUS_CONFIG[status] || STATUS_CONFIG[RecordStatus.PENDING];

  return (
    <View style={[styles.badge, { backgroundColor: config.bg }]}>
      <Text style={[styles.text, { color: config.color }]}>{config.label}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  badge: {
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: borderRadius.full,
    alignSelf: 'flex-start',
  },
  text: {
    fontSize: fontSize.xs,
    fontWeight: '600',
  },
});
