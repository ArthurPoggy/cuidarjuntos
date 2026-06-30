import React, { useState } from 'react';
import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
  Modal,
  ScrollView,
} from 'react-native';
import { SafeAreaView, useSafeAreaInsets } from 'react-native-safe-area-context';
import { useNavigation } from '@react-navigation/native';
import { useAuth } from '../contexts/AuthContext';
import { colors, spacing, fontSize, borderRadius } from '../theme';
import Svg, { Path } from 'react-native-svg';
import { useApiQuery } from '../hooks/useApiQuery';
import { notificationsApi } from '../api/endpoints';
import type { PaginatedResponse, Notification } from '../types/models';

interface Props {
  title?: string;
  showMenu?: boolean;
}

export default function Header({ title, showMenu = true }: Props) {
  const navigation = useNavigation<any>();
  const { user, group, logout } = useAuth();
  const [menuVisible, setMenuVisible] = useState(false);
  const insets = useSafeAreaInsets();

  // Contagem de não lidas para o badge. Buscada ao montar o Header e
  // guiada pelo cache do próprio fetch — sem forçar re-render por navegação.
  const { data: unreadData } = useApiQuery<PaginatedResponse<Notification>>(
    () => notificationsApi.list({ unread: 'true' }),
    []
  );
  const unreadCount = unreadData?.count ?? 0;

  const handleLogout = () => {
    setMenuVisible(false);
    logout();
  };

  return (
    <>
      <View style={[styles.header, { paddingTop: insets.top }]}>
        {/* Logo + Nome */}
        <TouchableOpacity
          style={styles.logo}
          onPress={() => navigation.navigate('Dashboard')}
          activeOpacity={0.7}
        >
          <View style={styles.logoIcon}>
            <Svg width={24} height={24} viewBox="0 0 24 24" fill="none">
              <Path
                d="M4.318 6.318a4.5 4.5 0 016.364 0L12 7.636l1.318-1.318a4.5 4.5 0 116.364 6.364L12 21.364l-7.682-7.682a4.5 4.5 0 010-6.364z"
                stroke="#FFFFFF"
                strokeWidth={2}
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </Svg>
          </View>
          <View style={styles.logoText}>
            <Text style={styles.logoTitle}>CuidarJuntos</Text>
          </View>
        </TouchableOpacity>

        {showMenu && (
          <View style={styles.actions}>
            {/* Sino de notificações com badge */}
            <TouchableOpacity
              style={styles.bellButton}
              onPress={() => navigation.navigate('Notifications')}
              activeOpacity={0.7}
              accessibilityLabel="Notificações"
            >
              <Svg width={24} height={24} viewBox="0 0 24 24" fill="none">
                <Path
                  d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9"
                  stroke={colors.text}
                  strokeWidth={2}
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </Svg>
              {unreadCount > 0 && (
                <View style={styles.badge}>
                  <Text style={styles.badgeText}>{unreadCount > 99 ? '99+' : unreadCount}</Text>
                </View>
              )}
            </TouchableOpacity>

            {/* Menu Hambúrguer */}
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
          </View>
        )}
      </View>

      {/* Menu Modal */}
      <Modal
        visible={menuVisible}
        animationType="slide"
        transparent={true}
        onRequestClose={() => setMenuVisible(false)}
      >
        <View style={styles.modalOverlay}>
          {/* Área clicável para fechar */}
          <TouchableOpacity
            style={styles.modalDismiss}
            activeOpacity={1}
            onPress={() => setMenuVisible(false)}
          />

          {/* Conteúdo do menu */}
          <View style={styles.modalContent}>
            <View style={styles.modalHeader}>
              <Text style={styles.modalTitle}>Menu</Text>
              <TouchableOpacity onPress={() => setMenuVisible(false)}>
                <Text style={styles.modalClose}>✕</Text>
              </TouchableOpacity>
            </View>

            <ScrollView>
              {/* Informação do Grupo */}
              {group && (
                <View style={styles.groupInfo}>
                  <Text style={styles.groupLabel}>Grupo Atual</Text>
                  <Text style={styles.groupName}>{group.name}</Text>
                  <Text style={styles.groupPatient}>
                    Paciente: {group.patient?.name}
                  </Text>
                </View>
              )}

              {/* Links de Navegação */}
              <TouchableOpacity
                style={styles.menuItem}
                onPress={() => {
                  setMenuVisible(false);
                  navigation.navigate('Dashboard');
                }}
              >
                <Text style={styles.menuItemText}>🏠  Dashboard</Text>
              </TouchableOpacity>

              <TouchableOpacity
                style={styles.menuItem}
                onPress={() => {
                  setMenuVisible(false);
                  navigation.navigate('RecordCreate');
                }}
              >
                <Text style={styles.menuItemText}>➕  Novo Registro</Text>
              </TouchableOpacity>

              <TouchableOpacity
                style={styles.menuItem}
                onPress={() => {
                  setMenuVisible(false);
                  navigation.navigate('Records');
                }}
              >
                <Text style={styles.menuItemText}>📋  Registros</Text>
              </TouchableOpacity>

              <TouchableOpacity
                style={styles.menuItem}
                onPress={() => {
                  setMenuVisible(false);
                  navigation.navigate('Medications');
                }}
              >
                <Text style={styles.menuItemText}>💊  Remédios</Text>
              </TouchableOpacity>

              <TouchableOpacity
                style={styles.menuItem}
                onPress={() => {
                  setMenuVisible(false);
                  navigation.navigate('Upcoming');
                }}
              >
                <Text style={styles.menuItemText}>📅  Agenda</Text>
              </TouchableOpacity>

              <TouchableOpacity
                style={styles.menuItem}
                onPress={() => {
                  setMenuVisible(false);
                  navigation.navigate('Notifications');
                }}
              >
                <Text style={styles.menuItemText}>
                  🔔  Notificações{unreadCount > 0 ? `  (${unreadCount})` : ''}
                </Text>
              </TouchableOpacity>

              <TouchableOpacity
                style={styles.menuItem}
                onPress={() => {
                  setMenuVisible(false);
                  navigation.navigate('Profile');
                }}
              >
                <Text style={styles.menuItemText}>👤  Perfil</Text>
              </TouchableOpacity>

              {/* Linha divisória */}
              <View style={styles.divider} />

              {/* Logout */}
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
  logo: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
  },
  logoIcon: {
    width: 40,
    height: 40,
    backgroundColor: colors.primary,
    borderRadius: borderRadius.md,
    justifyContent: 'center',
    alignItems: 'center',
  },
  logoText: {
    justifyContent: 'center',
  },
  logoTitle: {
    fontSize: fontSize.xl,
    fontWeight: '700',
    color: colors.text,
  },
  actions: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.xs,
  },
  bellButton: {
    padding: spacing.sm,
  },
  badge: {
    position: 'absolute',
    top: 2,
    right: 2,
    minWidth: 18,
    height: 18,
    paddingHorizontal: 4,
    borderRadius: 9,
    backgroundColor: colors.danger,
    justifyContent: 'center',
    alignItems: 'center',
  },
  badgeText: {
    color: colors.textInverse,
    fontSize: 10,
    fontWeight: '700',
  },
  menuButton: {
    padding: spacing.sm,
  },
  hamburger: {
    width: 24,
    height: 24,
    justifyContent: 'space-around',
  },
  hamburgerLine: {
    width: 24,
    height: 3,
    backgroundColor: colors.text,
    borderRadius: 2,
  },
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0, 0, 0, 0.5)',
    justifyContent: 'flex-end',
  },
  modalDismiss: {
    flex: 1,
  },
  modalContent: {
    backgroundColor: colors.surface,
    borderTopLeftRadius: borderRadius.xl,
    borderTopRightRadius: borderRadius.xl,
    maxHeight: '70%',
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
  modalTitle: {
    fontSize: fontSize.xl,
    fontWeight: '700',
    color: colors.text,
  },
  modalClose: {
    fontSize: fontSize.xxl,
    color: colors.textSecondary,
    width: 32,
    height: 32,
    textAlign: 'center',
    lineHeight: 32,
  },
  groupInfo: {
    backgroundColor: colors.borderLight,
    padding: spacing.md,
    margin: spacing.md,
    borderRadius: borderRadius.md,
  },
  groupLabel: {
    fontSize: fontSize.xs,
    color: colors.textSecondary,
    marginBottom: 4,
  },
  groupName: {
    fontSize: fontSize.md,
    fontWeight: '600',
    color: colors.text,
    marginBottom: 2,
  },
  groupPatient: {
    fontSize: fontSize.sm,
    color: colors.textSecondary,
  },
  menuItem: {
    paddingVertical: spacing.md,
    paddingHorizontal: spacing.lg,
    borderBottomWidth: 1,
    borderBottomColor: colors.borderLight,
  },
  menuItemText: {
    fontSize: fontSize.md,
    color: colors.text,
  },
  divider: {
    height: 8,
    backgroundColor: colors.background,
    marginVertical: spacing.sm,
  },
  menuItemDanger: {
    paddingVertical: spacing.md,
    paddingHorizontal: spacing.lg,
  },
  menuItemDangerText: {
    fontSize: fontSize.md,
    color: colors.danger,
    fontWeight: '600',
  },
});
