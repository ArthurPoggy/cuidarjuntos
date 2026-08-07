import React from 'react';
import { TouchableOpacity, Text, StyleSheet, TouchableOpacityProps } from 'react-native';
import { colors, spacing, borderRadius, fontSize } from '../theme';

interface Props extends TouchableOpacityProps {
  title: string;
}

export default function SecondaryButton({ title, disabled, style, ...touchableProps }: Props) {
  return (
    <TouchableOpacity
      style={[styles.button, disabled && styles.buttonDisabled, style]}
      disabled={disabled}
      activeOpacity={0.8}
      {...touchableProps}
    >
      <Text style={[styles.text, disabled && styles.textDisabled]}>{title}</Text>
    </TouchableOpacity>
  );
}

const styles = StyleSheet.create({
  button: {
    backgroundColor: colors.surface,
    borderRadius: borderRadius.md,
    borderWidth: 1,
    borderColor: colors.primary,
    paddingVertical: spacing.md,
    alignItems: 'center',
    justifyContent: 'center',
    minHeight: 50,
  },
  buttonDisabled: {
    borderColor: colors.border,
  },
  text: {
    color: colors.primary,
    fontSize: fontSize.lg,
    fontWeight: '600',
  },
  textDisabled: {
    color: colors.textMuted,
  },
});
