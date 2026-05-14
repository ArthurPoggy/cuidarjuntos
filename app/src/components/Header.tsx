import React, { useState } from 'react';
import {
  View, Text, TouchableOpacity, StyleSheet, Modal, ScrollView,
} from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { useNavigation, useNavigationState } from '@react-navigation/native';
import * as SecureStore from 'expo-secure-store';
import { useAuthStore } from '../stores/authStore';
import { useUnreadNotificationCount } from '../hooks/queries';
import { colors, spacing, fontSize, borderRadius } from '../theme';

interface Props {
  title?: string;
  showMenu?: boolean;
}

export default function Header({ showMenu = true }: Props) {
  const navigation = useNavigation<any>();
  // useNavigationState causes re-render on every navigation event,
  // which is what we want so the badge count stays fresh.
  useNavigationState((s) => s.index);

  const { user, group, reset } = useAuthStore();
  const [menuVisible, setMenuVisible] = useState(false);

  const { data: unreadCount = 0 } = useUnreadNotificationCount();
  const badgeCount = unreadCount > 99 ? 99 : unreadCount;

  const insets = useSafeAreaInsets();

  const handleLogout = async () => {
    setMenuVisible(false);
    await SecureStore.deleteItemAsync('access_token');
    await SecureStore.deleteItemAsync('refresh_token');
    reset();
  };

  const handleBellPress = () => {
    navigation.navigate('Notifications');
  };

  return (
    <>
      <View style={[styles.header, { paddingTop: insets.top }]}>
        {/* Logo */}
        <TouchableOpacity
          style={styles.logo}
          onPress={() => navigation.navigate('Dashboard')}
          activeOpacity={0.7}
        >
          <View style={styles.logoIcon}>
            <Text style={styles.logoEmoji}>❤️</Text>
          </View>
          <Text style={styles.logoTitle}>CuidarJuntos</Text>
        </TouchableOpacity>

        {/* Ações à direita */}
        <View style={styles.actions}>
          {/* Sino de notificações com badge */}
          <TouchableOpacity
            style={styles.bellButton}
            onPress={handleBellPress}
            activeOpacity={0.7}
            accessibilityLabel={
              badgeCount > 0
                ? `Notificações — ${badgeCount} não lida${badgeCount > 1 ? 's' : ''}`
                : 'Notificações'
            }
          >
            <Text style={styles.bellIcon}>🔔</Text>
            {badgeCount > 0 && (
              <View style={styles.badge}>
                <Text style={styles.badgeText}>{badgeCount}</Text>
              </View>
            )}
          </TouchableOpacity>

          {/* Hambúrguer */}
          {showMenu && (
            <TouchableOpacity
              style={styles.menuButton}
              onPress={() => setMenuVisible(true)}
              activeOpacity={0.7}
            >
              <View style={styles.hamburger}>
                <View style={styles.hamburgerLine} />
                <View style={styles.hamburgerLine} />
                <View style={styles.hamburgerLine} />
              </View>
            </TouchableOpacity>
          )}
        </View>
      </View>

      {/* Menu lateral */}
      <Modal
        visible={menuVisible}
        animationType="slide"
        transparent
        onRequestClose={() => setMenuVisible(false)}
      >
        <View style={styles.modalOverlay}>
          <TouchableOpacity
            style={styles.modalDismiss}
            activeOpacity={1}
            onPress={() => setMenuVisible(false)}
          />
          <View style={styles.modalContent}>
            <View style={styles.modalHeader}>
              <Text style={styles.modalTitle}>Menu</Text>
              <TouchableOpacity onPress={() => setMenuVisible(false)}>
                <Text style={styles.modalClose}>✕</Text>
              </TouchableOpacity>
            </View>

            <ScrollView>
              {group && (
                <View style={styles.groupInfo}>
                  <Text style={styles.groupLabel}>Grupo Atual</Text>
                  <Text style={styles.groupName}>{group.name}</Text>
                  <Text style={styles.groupPatient}>Paciente: {group.patient?.name}</Text>
                </View>
              )}

              {[
                { screen: 'Dashboard', label: '🏠  Dashboard' },
                { screen: 'RecordCreate', label: '➕  Novo Registro' },
                { screen: 'Records', label: '📋  Registros' },
                { screen: 'Medications', label: '💊  Remédios' },
                { screen: 'Upcoming', label: '📅  Agenda' },
                { screen: 'Shifts', label: '🗓️  Escala' },
                { screen: 'Checklist', label: '✅  Tarefas' },
                { screen: 'Notifications', label: '🔔  Notificações' },
                { screen: 'Profile', label: '👤  Perfil' },
              ].map(({ screen, label }) => (
                <TouchableOpacity
                  key={screen}
                  style={styles.menuItem}
                  onPress={() => { setMenuVisible(false); navigation.navigate(screen as any); }}
                >
                  <View style={styles.menuItemRow}>
                    <Text style={styles.menuItemText}>{label}</Text>
                    {screen === 'Notifications' && badgeCount > 0 && (
                      <View style={styles.menuBadge}>
                        <Text style={styles.menuBadgeText}>{badgeCount}</Text>
                      </View>
                    )}
                  </View>
                </TouchableOpacity>
              ))}

              <View style={styles.divider} />

              <TouchableOpacity style={styles.menuItemDanger} onPress={handleLogout}>
                <Text style={styles.menuItemDangerText}>🚪  Sair</Text>
              </TouchableOpacity>
            </ScrollView>
          </View>
        </View>
      </Modal>
    </>
  );
}

const BADGE_SIZE = 18;

const styles = StyleSheet.create({
  header: {
    backgroundColor: colors.surface,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: spacing.md,
    paddingBottom: spacing.sm,
  },
  logo: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
  logoIcon: {
    width: 36, height: 36,
    backgroundColor: colors.primary,
    borderRadius: borderRadius.md,
    justifyContent: 'center', alignItems: 'center',
  },
  logoEmoji: { fontSize: 18 },
  logoTitle: { fontSize: fontSize.xl, fontWeight: '700', color: colors.text },

  actions: { flexDirection: 'row', alignItems: 'center', gap: spacing.xs },

  bellButton: {
    width: 40, height: 40,
    justifyContent: 'center', alignItems: 'center',
  },
  bellIcon: { fontSize: 22 },
  badge: {
    position: 'absolute',
    top: 2,
    right: 2,
    minWidth: BADGE_SIZE,
    height: BADGE_SIZE,
    borderRadius: BADGE_SIZE / 2,
    backgroundColor: colors.danger,
    justifyContent: 'center',
    alignItems: 'center',
    paddingHorizontal: 4,
    borderWidth: 1.5,
    borderColor: colors.surface,
  },
  badgeText: {
    color: colors.textInverse,
    fontSize: 10,
    fontWeight: '700',
    lineHeight: 13,
  },

  menuButton: { padding: spacing.sm },
  hamburger: { width: 24, height: 24, justifyContent: 'space-around' },
  hamburgerLine: { width: 24, height: 3, backgroundColor: colors.text, borderRadius: 2 },

  modalOverlay: { flex: 1, backgroundColor: 'rgba(0,0,0,0.5)', justifyContent: 'flex-end' },
  modalDismiss: { flex: 1 },
  modalContent: {
    backgroundColor: colors.surface,
    borderTopLeftRadius: borderRadius.xl,
    borderTopRightRadius: borderRadius.xl,
    maxHeight: '75%',
    paddingBottom: spacing.xl,
  },
  modalHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: spacing.lg,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  modalTitle: { fontSize: fontSize.xl, fontWeight: '700', color: colors.text },
  modalClose: { fontSize: fontSize.xxl, color: colors.textSecondary },
  groupInfo: {
    backgroundColor: colors.borderLight,
    padding: spacing.md,
    margin: spacing.md,
    borderRadius: borderRadius.md,
  },
  groupLabel: { fontSize: fontSize.xs, color: colors.textSecondary, marginBottom: 4 },
  groupName: { fontSize: fontSize.md, fontWeight: '600', color: colors.text, marginBottom: 2 },
  groupPatient: { fontSize: fontSize.sm, color: colors.textSecondary },

  menuItem: {
    paddingVertical: spacing.md,
    paddingHorizontal: spacing.lg,
    borderBottomWidth: 1,
    borderBottomColor: colors.borderLight,
  },
  menuItemRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  menuItemText: { fontSize: fontSize.md, color: colors.text },
  menuBadge: {
    minWidth: BADGE_SIZE,
    height: BADGE_SIZE,
    borderRadius: BADGE_SIZE / 2,
    backgroundColor: colors.danger,
    justifyContent: 'center',
    alignItems: 'center',
    paddingHorizontal: 5,
  },
  menuBadgeText: { color: colors.textInverse, fontSize: 10, fontWeight: '700' },

  divider: { height: 8, backgroundColor: colors.background, marginVertical: spacing.sm },
  menuItemDanger: { paddingVertical: spacing.md, paddingHorizontal: spacing.lg },
  menuItemDangerText: { fontSize: fontSize.md, color: colors.danger, fontWeight: '600' },
});
