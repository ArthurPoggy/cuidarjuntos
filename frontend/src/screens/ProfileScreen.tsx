import React, { useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  Alert,
  ActivityIndicator,
  ScrollView,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useNavigation } from '@react-navigation/native';
import { useAuth } from '../contexts/AuthContext';
import { groupsApi } from '../api/endpoints';
import { colors, spacing, fontSize, borderRadius } from '../theme';

export default function ProfileScreen() {
  const navigation = useNavigation<any>();
  const { user, group, logout, refreshGroup } = useAuth();
  const [leavingGroup, setLeavingGroup] = useState(false);
  const [loggingOut, setLoggingOut] = useState(false);

  const handleLeaveGroup = () => {
    Alert.alert(
      'Sair do Grupo',
      'Tem certeza que deseja sair do grupo? Voce perdera acesso aos registros.',
      [
        { text: 'Cancelar', style: 'cancel' },
        {
          text: 'Sair',
          style: 'destructive',
          onPress: async () => {
            setLeavingGroup(true);
            try {
              await groupsApi.leave();
              await refreshGroup();
            } catch {
              Alert.alert('Erro', 'Nao foi possivel sair do grupo.');
            } finally {
              setLeavingGroup(false);
            }
          },
        },
      ],
    );
  };

  const handleLogout = async () => {
    setLoggingOut(true);
    try {
      await logout();
    } catch {
      Alert.alert('Erro', 'Nao foi possivel fazer logout.');
    } finally {
      setLoggingOut(false);
    }
  };

  const isSuperuser = (user as any)?.is_superuser ?? false;

  return (
    <SafeAreaView style={styles.safe}>
      <ScrollView contentContainerStyle={styles.scrollContent}>
        {/* User section */}
        <View style={styles.card}>
          <View style={styles.avatarCircle}>
            <Text style={styles.avatarText}>
              {user?.profile?.full_name?.charAt(0)?.toUpperCase() || user?.username?.charAt(0)?.toUpperCase() || '?'}
            </Text>
          </View>
          <Text style={styles.userName}>
            {user?.profile?.full_name || `${user?.first_name ?? ''} ${user?.last_name ?? ''}`.trim() || user?.username || '---'}
          </Text>
          <Text style={styles.userEmail}>{user?.email || '---'}</Text>

          <View style={styles.divider} />

          <View style={styles.infoRow}>
            <Text style={styles.infoLabel}>Usuario:</Text>
            <Text style={styles.infoValue}>{user?.username || '---'}</Text>
          </View>
          {user?.profile?.cpf ? (
            <View style={styles.infoRow}>
              <Text style={styles.infoLabel}>CPF:</Text>
              <Text style={styles.infoValue}>{user.profile.cpf}</Text>
            </View>
          ) : null}
          {user?.profile?.birth_date ? (
            <View style={styles.infoRow}>
              <Text style={styles.infoLabel}>Nascimento:</Text>
              <Text style={styles.infoValue}>{user.profile.birth_date}</Text>
            </View>
          ) : null}
          {user?.profile?.role ? (
            <View style={styles.infoRow}>
              <Text style={styles.infoLabel}>Papel:</Text>
              <Text style={styles.infoValue}>{user.profile.role}</Text>
            </View>
          ) : null}
        </View>

        {/* Group section */}
        {group ? (
          <View style={styles.card}>
            <Text style={styles.cardTitle}>Grupo</Text>
            <View style={styles.infoRow}>
              <Text style={styles.infoLabel}>Nome:</Text>
              <Text style={styles.infoValue}>{group.name}</Text>
            </View>
            <View style={styles.infoRow}>
              <Text style={styles.infoLabel}>Paciente:</Text>
              <Text style={styles.infoValue}>{group.patient?.name || '---'}</Text>
            </View>
            <View style={styles.infoRow}>
              <Text style={styles.infoLabel}>Membros:</Text>
              <Text style={styles.infoValue}>{group.member_count ?? '---'}</Text>
            </View>
            {user?.membership?.relation_to_patient ? (
              <View style={styles.infoRow}>
                <Text style={styles.infoLabel}>Relacao:</Text>
                <Text style={styles.infoValue}>{user.membership.relation_to_patient}</Text>
              </View>
            ) : null}

            <TouchableOpacity
              style={[styles.leaveButton, leavingGroup && { backgroundColor: '#FCA5A5' }]}
              onPress={handleLeaveGroup}
              disabled={leavingGroup}
              activeOpacity={0.7}
            >
              {leavingGroup ? (
                <ActivityIndicator color={colors.textInverse} size="small" />
              ) : (
                <Text style={styles.leaveButtonText}>Sair do Grupo</Text>
              )}
            </TouchableOpacity>
          </View>
        ) : (
          <View style={styles.card}>
            <Text style={styles.cardTitle}>Grupo</Text>
            <Text style={styles.noGroupText}>Voce nao esta em nenhum grupo.</Text>
          </View>
        )}

        {/* Admin link */}
        {isSuperuser && (
          <TouchableOpacity
            style={styles.adminButton}
            onPress={() => navigation.navigate('AdminOverview')}
            activeOpacity={0.7}
          >
            <Text style={styles.adminButtonText}>Painel Administrativo</Text>
          </TouchableOpacity>
        )}

        {/* Logout */}
        <TouchableOpacity
          style={[styles.logoutButton, loggingOut && { backgroundColor: colors.primaryLight }]}
          onPress={handleLogout}
          disabled={loggingOut}
          activeOpacity={0.7}
        >
          {loggingOut ? (
            <ActivityIndicator color={colors.textInverse} size="small" />
          ) : (
            <Text style={styles.logoutButtonText}>Logout</Text>
          )}
        </TouchableOpacity>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: {
    flex: 1,
    backgroundColor: colors.background,
  },
  scrollContent: {
    padding: spacing.lg,
    paddingBottom: spacing.xxl,
  },
  card: {
    backgroundColor: colors.card,
    borderRadius: borderRadius.lg,
    padding: spacing.lg,
    marginBottom: spacing.md,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.08,
    shadowRadius: 8,
    elevation: 3,
    alignItems: 'center',
  },
  avatarCircle: {
    width: 72,
    height: 72,
    borderRadius: 36,
    backgroundColor: colors.primary,
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: spacing.md,
  },
  avatarText: {
    color: colors.textInverse,
    fontSize: fontSize.xxl,
    fontWeight: '700',
  },
  userName: {
    fontSize: fontSize.xl,
    fontWeight: '600',
    color: colors.text,
    textAlign: 'center',
  },
  userEmail: {
    fontSize: fontSize.sm,
    color: colors.textSecondary,
    marginTop: spacing.xs,
  },
  divider: {
    height: 1,
    backgroundColor: colors.divider,
    width: '100%',
    marginVertical: spacing.md,
  },
  infoRow: {
    flexDirection: 'row',
    width: '100%',
    marginBottom: spacing.xs,
  },
  infoLabel: {
    fontSize: fontSize.sm,
    color: colors.textSecondary,
    fontWeight: '500',
    width: 100,
  },
  infoValue: {
    flex: 1,
    fontSize: fontSize.sm,
    color: colors.text,
  },
  cardTitle: {
    fontSize: fontSize.lg,
    fontWeight: '600',
    color: colors.text,
    marginBottom: spacing.md,
    alignSelf: 'flex-start',
  },
  noGroupText: {
    fontSize: fontSize.sm,
    color: colors.textSecondary,
  },
  leaveButton: {
    backgroundColor: colors.danger,
    borderRadius: borderRadius.md,
    paddingVertical: spacing.sm + 2,
    paddingHorizontal: spacing.lg,
    marginTop: spacing.md,
    alignItems: 'center',
    justifyContent: 'center',
    width: '100%',
    minHeight: 44,
  },
  leaveButtonText: {
    color: colors.textInverse,
    fontSize: fontSize.md,
    fontWeight: '600',
  },
  adminButton: {
    backgroundColor: colors.secondary,
    borderRadius: borderRadius.md,
    paddingVertical: spacing.md,
    alignItems: 'center',
    marginBottom: spacing.md,
  },
  adminButtonText: {
    color: colors.textInverse,
    fontSize: fontSize.md,
    fontWeight: '600',
  },
  logoutButton: {
    backgroundColor: colors.text,
    borderRadius: borderRadius.md,
    paddingVertical: spacing.md,
    alignItems: 'center',
    minHeight: 50,
    justifyContent: 'center',
  },
  logoutButtonText: {
    color: colors.textInverse,
    fontSize: fontSize.md,
    fontWeight: '600',
  },
});
