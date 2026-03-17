import React from 'react';
import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useNavigation } from '@react-navigation/native';
import { useAuth } from '../contexts/AuthContext';
import { colors, spacing, fontSize, borderRadius } from '../theme';

export default function ChooseGroupScreen() {
  const navigation = useNavigation<any>();
  const { user, logout } = useAuth();

  return (
    <SafeAreaView style={styles.safe}>
      <View style={styles.container}>
        <View style={styles.header}>
          <Text style={styles.greeting}>
            Ola, {user?.profile?.full_name || user?.username || 'Usuario'}!
          </Text>
          <Text style={styles.subtitle}>
            Para comecar, crie um novo grupo de cuidado ou entre em um grupo existente.
          </Text>
        </View>

        <View style={styles.cardsContainer}>
          <TouchableOpacity
            style={styles.card}
            onPress={() => navigation.navigate('CreateGroup')}
            activeOpacity={0.8}
          >
            <View style={styles.cardIconContainer}>
              <Text style={styles.cardIcon}>+</Text>
            </View>
            <Text style={styles.cardTitle}>Criar Grupo</Text>
            <Text style={styles.cardDescription}>
              Crie um novo grupo de cuidado e convide familiares e cuidadores.
            </Text>
          </TouchableOpacity>

          <TouchableOpacity
            style={styles.card}
            onPress={() => navigation.navigate('JoinGroup')}
            activeOpacity={0.8}
          >
            <View style={[styles.cardIconContainer, styles.cardIconSecondary]}>
              <Text style={styles.cardIcon}>&#x2192;</Text>
            </View>
            <Text style={styles.cardTitle}>Entrar em Grupo</Text>
            <Text style={styles.cardDescription}>
              Entre em um grupo existente usando o PIN fornecido pelo administrador.
            </Text>
          </TouchableOpacity>
        </View>

        <TouchableOpacity
          style={styles.logoutButton}
          onPress={logout}
          activeOpacity={0.7}
        >
          <Text style={styles.logoutText}>Sair da Conta</Text>
        </TouchableOpacity>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: {
    flex: 1,
    backgroundColor: colors.background,
  },
  container: {
    flex: 1,
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.xl,
    justifyContent: 'center',
  },
  header: {
    alignItems: 'center',
    marginBottom: spacing.xl,
  },
  greeting: {
    fontSize: fontSize.xl,
    fontWeight: '700',
    color: colors.text,
    marginBottom: spacing.sm,
    textAlign: 'center',
  },
  subtitle: {
    fontSize: fontSize.sm,
    color: colors.textSecondary,
    textAlign: 'center',
    lineHeight: 20,
    paddingHorizontal: spacing.md,
  },
  cardsContainer: {
    gap: spacing.md,
  },
  card: {
    backgroundColor: colors.surface,
    borderRadius: borderRadius.lg,
    padding: spacing.lg,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.08,
    shadowRadius: 8,
    elevation: 3,
    alignItems: 'center',
    marginBottom: spacing.md,
  },
  cardIconContainer: {
    width: 56,
    height: 56,
    borderRadius: borderRadius.full,
    backgroundColor: colors.primary,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: spacing.md,
  },
  cardIconSecondary: {
    backgroundColor: colors.secondary,
  },
  cardIcon: {
    fontSize: fontSize.xxl,
    color: colors.textInverse,
    fontWeight: '700',
  },
  cardTitle: {
    fontSize: fontSize.lg,
    fontWeight: '600',
    color: colors.text,
    marginBottom: spacing.xs,
  },
  cardDescription: {
    fontSize: fontSize.sm,
    color: colors.textSecondary,
    textAlign: 'center',
    lineHeight: 20,
  },
  logoutButton: {
    alignItems: 'center',
    paddingVertical: spacing.md,
    marginTop: spacing.xl,
  },
  logoutText: {
    color: colors.danger,
    fontSize: fontSize.md,
    fontWeight: '500',
  },
});
