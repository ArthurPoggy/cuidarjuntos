import React from 'react';
import { TouchableOpacity, Text, StyleSheet, View } from 'react-native';
import { colors, spacing, borderRadius, fontSize } from '../theme';
import { CATEGORY_META } from '../utils/constants';

interface Props {
  type: string;
  count: number;
  selected: boolean;
  hasSelection: boolean;
  onPress: () => void;
}

export default function CategoryCard({ type, count, selected, hasSelection, onPress }: Props) {
  const meta = CATEGORY_META[type];
  if (!meta) return null;

  // Opacidade: se tem seleção e NÃO está selecionado, fica com 45% de opacidade
  const opacity = hasSelection && !selected ? 0.45 : 1;

  return (
    <TouchableOpacity
      style={[
        styles.card,
        {
          backgroundColor: meta.bg,
          borderColor: selected ? meta.color : colors.border,
          opacity,
        },
      ]}
      onPress={onPress}
      activeOpacity={0.7}
    >
      <Text style={styles.icon}>{meta.icon}</Text>
      <Text style={[styles.count, { color: meta.color }]}>{count}</Text>
      <Text style={styles.label} numberOfLines={2}>{meta.label}</Text>
    </TouchableOpacity>
  );
}

const styles = StyleSheet.create({
  card: {
    // Grid responsivo (será aplicado no parent)
    padding: spacing.lg,
    borderRadius: borderRadius.xl,
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 2,
    minHeight: 120,
  },
  icon: {
    fontSize: 32,
    marginBottom: spacing.xs,
  },
  count: {
    fontSize: fontSize.xxl,
    fontWeight: '700',
    marginBottom: 4,
  },
  label: {
    fontSize: fontSize.sm,
    color: colors.textSecondary,
    textAlign: 'center',
    fontWeight: '500',
  },
});
