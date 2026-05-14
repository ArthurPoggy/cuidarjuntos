import React, { useState } from 'react';
import {
  View, Text, TouchableOpacity, StyleSheet, Modal, ScrollView,
} from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { useNavigation } from '@react-navigation/native';
import * as SecureStore from 'expo-secure-store';
import { useAuthStore } from '../stores/authStore';
import { colors, spacing, fontSize, borderRadius } from '../theme';

interface Props {
  title?: string;
  showMenu?: boolean;
}

export default function Header({ showMenu = true }: Props) {
  const navigation = useNavigation<any>();
  const { user, group, reset } = useAuthStore();
  const [menuVisible, setMenuVisible] = useState(false);
  const insets = useSafeAreaInsets();

  const handleLogout = async () => {
    setMenuVisible(false);
    await SecureStore.deleteItemAsync('access_token');
    await SecureStore.deleteItemAsync('refresh_token');
    reset();
  };

  return (
    <>
      <View style={[styles.header, { paddingTop: insets.top }]}>
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
                  <Text style={styles.menuItemText}>{label}</Text>
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
  menuItemText: { fontSize: fontSize.md, color: colors.text },
  divider: { height: 8, backgroundColor: colors.background, marginVertical: spacing.sm },
  menuItemDanger: { paddingVertical: spacing.md, paddingHorizontal: spacing.lg },
  menuItemDangerText: { fontSize: fontSize.md, color: colors.danger, fontWeight: '600' },
});
