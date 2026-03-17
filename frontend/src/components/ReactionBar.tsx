import React from 'react';
import { View, TouchableOpacity, Text, StyleSheet } from 'react-native';
import { colors, spacing, borderRadius, fontSize } from '../theme';
import { REACTION_OPTIONS } from '../utils/constants';

interface Props {
  counts: Record<string, number>;
  userReaction: string;
  onReact: (code: string) => void;
}

export default function ReactionBar({ counts, userReaction, onReact }: Props) {
  return (
    <View style={styles.container}>
      {REACTION_OPTIONS.map(({ code, emoji, label }) => {
        const count = counts[code] || 0;
        const isActive = userReaction === code;
        return (
          <TouchableOpacity
            key={code}
            style={[styles.btn, isActive && styles.btnActive]}
            onPress={() => onReact(code)}
          >
            <Text style={styles.emoji}>{emoji}</Text>
            {count > 0 && <Text style={styles.count}>{count}</Text>}
          </TouchableOpacity>
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flexDirection: 'row',
    gap: spacing.sm,
  },
  btn: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderRadius: borderRadius.full,
    backgroundColor: colors.borderLight,
    gap: 4,
  },
  btnActive: {
    backgroundColor: '#DBEAFE',
    borderWidth: 1,
    borderColor: colors.primary,
  },
  emoji: {
    fontSize: 16,
  },
  count: {
    fontSize: fontSize.xs,
    color: colors.textSecondary,
    fontWeight: '600',
  },
});
