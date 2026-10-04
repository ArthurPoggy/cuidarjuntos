import React from 'react';
import { Linking, Platform, Pressable, StyleSheet, Text, View } from 'react-native';
import { borderRadius, colors, fontSize, spacing } from '../theme';
import { useAppVersionCheck } from '../hooks/useAppVersionCheck';

/**
 * Aviso de nova versão. Na web o usuário já recebe sempre o build mais recente
 * (deploy na Vercel), então o aviso só aparece no app nativo. Obrigatória
 * (`required`) usa a cor de erro; recomendada, a cor primária.
 */
export default function UpdateBanner() {
  const { status, info } = useAppVersionCheck();
  if (Platform.OS === 'web' || status === 'ok' || !info) return null;

  const required = status === 'required';
  const message = required
    ? 'Esta versão do app não é mais compatível. Atualize para continuar.'
    : `Nova versão disponível (${info.version}).`;

  return (
    <View
      style={[styles.banner, required ? styles.required : styles.recommended]}
      accessibilityRole="alert"
    >
      <Text style={styles.text}>{message}</Text>
      {!!info.update_url && (
        <Pressable onPress={() => Linking.openURL(info.update_url)} accessibilityRole="link">
          <Text style={styles.link}>Atualizar</Text>
        </Pressable>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  banner: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: spacing.md,
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.sm,
    borderRadius: borderRadius.md,
  },
  recommended: { backgroundColor: colors.primary },
  required: { backgroundColor: colors.danger },
  text: { flex: 1, color: colors.textInverse, fontSize: fontSize.sm },
  link: { color: colors.textInverse, fontSize: fontSize.sm, fontWeight: '700', textDecorationLine: 'underline' },
});
