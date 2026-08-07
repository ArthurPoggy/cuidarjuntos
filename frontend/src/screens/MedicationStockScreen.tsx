import React, { useCallback, useEffect, useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ActivityIndicator,
  FlatList,
  TouchableOpacity,
  TextInput,
  Modal,
  Alert,
  RefreshControl,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { medicationsApi } from '../api/endpoints';
import { colors, spacing, fontSize, borderRadius } from '../theme';
import type { MedicationWithStock, StockSection } from '../types/models';
import FormField from '../components/FormField';
import PrimaryButton from '../components/PrimaryButton';
import SecondaryButton from '../components/SecondaryButton';

const SECTION_COLORS: Record<string, { bg: string; accent: string; label: string }> = {
  danger: { bg: '#FEF2F2', accent: colors.stockDanger, label: 'Estoque Critico' },
  warn: { bg: '#FEFCE8', accent: colors.stockWarn, label: 'Estoque Baixo' },
  ok: { bg: '#F0FDF4', accent: colors.stockOk, label: 'Estoque OK' },
};

export default function MedicationStockScreen() {
  const [sections, setSections] = useState<StockSection[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState('');
  const [search, setSearch] = useState('');

  // Add stock modal
  const [addStockVisible, setAddStockVisible] = useState(false);
  const [addStockMed, setAddStockMed] = useState<MedicationWithStock | null>(null);
  const [addStockQty, setAddStockQty] = useState('');
  const [addingStock, setAddingStock] = useState(false);

  // Create medication modal
  const [createVisible, setCreateVisible] = useState(false);
  const [newName, setNewName] = useState('');
  const [newDosage, setNewDosage] = useState('');
  const [creating, setCreating] = useState(false);
  const [newNameError, setNewNameError] = useState('');
  const [newDosageError, setNewDosageError] = useState('');

  const fetchStock = useCallback(async () => {
    try {
      setError('');
      const params: Record<string, string> = {};
      if (search.trim()) params.search = search.trim();
      const res = await medicationsApi.stockOverview(params);
      setSections(res.data.sections);
    } catch {
      setError('Erro ao carregar estoque de medicamentos.');
    }
  }, [search]);

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      await fetchStock();
      setLoading(false);
    };
    load();
  }, [fetchStock]);

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    await fetchStock();
    setRefreshing(false);
  }, [fetchStock]);

  const handleAddStock = async () => {
    if (!addStockMed || !addStockQty.trim()) return;
    const qty = Number(addStockQty);
    if (isNaN(qty) || qty <= 0) {
      Alert.alert('Erro', 'Informe uma quantidade valida.');
      return;
    }
    setAddingStock(true);
    try {
      await medicationsApi.addStock(addStockMed.id, qty);
      setAddStockVisible(false);
      setAddStockQty('');
      setAddStockMed(null);
      await fetchStock();
    } catch {
      Alert.alert('Erro', 'Nao foi possivel adicionar estoque.');
    } finally {
      setAddingStock(false);
    }
  };

  const handleCreateMedication = async () => {
    const nameError = newName.trim() ? '' : 'Informe o nome do medicamento.';
    const dosageError = newDosage.trim() ? '' : 'Informe a dosagem do medicamento.';
    setNewNameError(nameError);
    setNewDosageError(dosageError);
    if (nameError || dosageError) {
      return;
    }
    setCreating(true);
    try {
      await medicationsApi.create({ name: newName.trim(), dosage: newDosage.trim() });
      closeCreateModal();
      await fetchStock();
    } catch {
      Alert.alert('Erro', 'Nao foi possivel criar o medicamento.');
    } finally {
      setCreating(false);
    }
  };

  const closeCreateModal = () => {
    setCreateVisible(false);
    setNewName('');
    setNewDosage('');
    setNewNameError('');
    setNewDosageError('');
  };

  const openAddStock = (med: MedicationWithStock) => {
    setAddStockMed(med);
    setAddStockQty('');
    setAddStockVisible(true);
  };

  // Flatten sections into FlatList data with section headers
  type ListItem =
    | { kind: 'header'; key: string; title: string; accent: string; bg: string }
    | { kind: 'item'; key: string; med: MedicationWithStock; accent: string };

  const flatData: ListItem[] = [];
  for (const section of sections) {
    const sColors = SECTION_COLORS[section.key] ?? SECTION_COLORS.ok;
    if (section.items.length === 0) continue;
    flatData.push({
      kind: 'header',
      key: `header-${section.key}`,
      title: sColors.label,
      accent: sColors.accent,
      bg: sColors.bg,
    });
    for (const med of section.items) {
      flatData.push({
        kind: 'item',
        key: `item-${med.id}`,
        med,
        accent: sColors.accent,
      });
    }
  }

  const renderItem = ({ item }: { item: ListItem }) => {
    if (item.kind === 'header') {
      return (
        <View style={[styles.sectionHeader, { backgroundColor: item.bg }]}>
          <View style={[styles.sectionDot, { backgroundColor: item.accent }]} />
          <Text style={[styles.sectionTitle, { color: item.accent }]}>{item.title}</Text>
        </View>
      );
    }

    const { med, accent } = item;
    return (
      <View style={styles.medCard}>
        <View style={styles.medInfo}>
          <Text style={styles.medName}>{med.name}</Text>
          <Text style={styles.medDosage}>{med.dosage}</Text>
        </View>
        <View style={styles.medStockContainer}>
          <Text style={[styles.medStock, { color: accent }]}>{med.current_stock}</Text>
          <Text style={styles.medStockLabel}>un.</Text>
        </View>
        <TouchableOpacity
          style={[styles.addStockBtn, { borderColor: accent }]}
          onPress={() => openAddStock(med)}
          activeOpacity={0.7}
        >
          <Text style={[styles.addStockBtnText, { color: accent }]}>+ Estoque</Text>
        </TouchableOpacity>
      </View>
    );
  };

  if (loading) {
    return (
      <SafeAreaView style={styles.safe}>
        <View style={styles.center}>
          <ActivityIndicator size="large" color={colors.primary} />
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.safe}>
      {/* Search bar */}
      <View style={styles.searchRow}>
        <TextInput
          style={styles.searchInput}
          placeholder="Buscar medicamento..."
          placeholderTextColor={colors.textMuted}
          value={search}
          onChangeText={setSearch}
          returnKeyType="search"
          onSubmitEditing={fetchStock}
        />
        <TouchableOpacity
          style={styles.createButton}
          onPress={() => {
            setNewNameError('');
            setNewDosageError('');
            setCreateVisible(true);
          }}
          activeOpacity={0.7}
        >
          <Text style={styles.createButtonText}>+ Novo</Text>
        </TouchableOpacity>
      </View>

      <FlatList
        data={flatData}
        keyExtractor={(item) => item.key}
        renderItem={renderItem}
        contentContainerStyle={styles.listContent}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} colors={[colors.primary]} />
        }
        ListEmptyComponent={
          <View style={styles.emptyContainer}>
            <Text style={styles.emptyText}>
              {error || 'Nenhum medicamento encontrado.'}
            </Text>
          </View>
        }
      />

      {/* Add Stock Modal */}
      <Modal
        visible={addStockVisible}
        transparent
        animationType="fade"
        onRequestClose={() => setAddStockVisible(false)}
      >
        <View style={styles.modalOverlay}>
          <View style={styles.modalCard}>
            <Text style={styles.modalTitle}>Adicionar Estoque</Text>
            <Text style={styles.modalSubtitle}>
              {addStockMed?.name} - {addStockMed?.dosage}
            </Text>
            <Text style={styles.label}>Quantidade</Text>
            <TextInput
              style={styles.modalInput}
              value={addStockQty}
              onChangeText={setAddStockQty}
              placeholder="Ex: 30"
              placeholderTextColor={colors.textMuted}
              keyboardType="numeric"
              autoFocus
            />
            <View style={styles.modalActions}>
              <TouchableOpacity
                style={styles.modalCancelBtn}
                onPress={() => setAddStockVisible(false)}
              >
                <Text style={styles.modalCancelText}>Cancelar</Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={[styles.modalConfirmBtn, addingStock && { backgroundColor: colors.primaryLight }]}
                onPress={handleAddStock}
                disabled={addingStock}
              >
                {addingStock ? (
                  <ActivityIndicator color={colors.textInverse} size="small" />
                ) : (
                  <Text style={styles.modalConfirmText}>Adicionar</Text>
                )}
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>

      {/* Create Medication Modal */}
      <Modal
        visible={createVisible}
        transparent
        animationType="fade"
        onRequestClose={closeCreateModal}
      >
        <View style={styles.modalOverlay}>
          <View style={styles.modalCard}>
            <Text style={styles.modalTitle}>Novo Medicamento</Text>
            <FormField
              label="Nome"
              value={newName}
              onChangeText={(text) => {
                setNewName(text);
                if (newNameError) setNewNameError('');
              }}
              placeholder="Ex: Paracetamol"
              error={newNameError}
              autoFocus
            />
            <FormField
              label="Dosagem"
              value={newDosage}
              onChangeText={(text) => {
                setNewDosage(text);
                if (newDosageError) setNewDosageError('');
              }}
              placeholder="Ex: 500mg"
              error={newDosageError}
            />
            <View style={styles.modalActions}>
              <SecondaryButton
                title="Cancelar"
                onPress={closeCreateModal}
                style={styles.modalActionBtn}
              />
              <PrimaryButton
                title="Criar"
                onPress={handleCreateMedication}
                loading={creating}
                style={styles.modalActionBtn}
              />
            </View>
          </View>
        </View>
      </Modal>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: {
    flex: 1,
    backgroundColor: colors.background,
  },
  center: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  searchRow: {
    flexDirection: 'row',
    paddingHorizontal: spacing.md,
    paddingTop: spacing.md,
    paddingBottom: spacing.sm,
    gap: spacing.sm,
  },
  searchInput: {
    flex: 1,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: borderRadius.md,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    fontSize: fontSize.sm,
    color: colors.text,
  },
  createButton: {
    backgroundColor: colors.primary,
    borderRadius: borderRadius.md,
    paddingHorizontal: spacing.md,
    justifyContent: 'center',
    alignItems: 'center',
  },
  createButtonText: {
    color: colors.textInverse,
    fontSize: fontSize.sm,
    fontWeight: '600',
  },
  listContent: {
    paddingHorizontal: spacing.md,
    paddingBottom: spacing.lg,
  },
  sectionHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    borderRadius: borderRadius.md,
    marginTop: spacing.md,
    marginBottom: spacing.xs,
  },
  sectionDot: {
    width: 10,
    height: 10,
    borderRadius: 5,
    marginRight: spacing.sm,
  },
  sectionTitle: {
    fontSize: fontSize.md,
    fontWeight: '600',
  },
  medCard: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.card,
    borderRadius: borderRadius.md,
    padding: spacing.md,
    marginBottom: spacing.sm,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.05,
    shadowRadius: 3,
    elevation: 1,
  },
  medInfo: {
    flex: 1,
  },
  medName: {
    fontSize: fontSize.md,
    fontWeight: '600',
    color: colors.text,
  },
  medDosage: {
    fontSize: fontSize.sm,
    color: colors.textSecondary,
    marginTop: 2,
  },
  medStockContainer: {
    alignItems: 'center',
    marginHorizontal: spacing.sm,
  },
  medStock: {
    fontSize: fontSize.xl,
    fontWeight: '700',
  },
  medStockLabel: {
    fontSize: fontSize.xs,
    color: colors.textMuted,
  },
  addStockBtn: {
    borderWidth: 1,
    borderRadius: borderRadius.md,
    paddingHorizontal: spacing.sm,
    paddingVertical: spacing.xs + 2,
  },
  addStockBtnText: {
    fontSize: fontSize.xs,
    fontWeight: '600',
  },
  emptyContainer: {
    alignItems: 'center',
    paddingVertical: spacing.xxl,
  },
  emptyText: {
    fontSize: fontSize.md,
    color: colors.textSecondary,
  },
  // Modal
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.4)',
    justifyContent: 'center',
    alignItems: 'center',
    padding: spacing.lg,
  },
  modalCard: {
    backgroundColor: colors.surface,
    borderRadius: borderRadius.lg,
    padding: spacing.lg,
    width: '100%',
    maxWidth: 400,
  },
  modalTitle: {
    fontSize: fontSize.xl,
    fontWeight: '600',
    color: colors.text,
    marginBottom: spacing.xs,
  },
  modalSubtitle: {
    fontSize: fontSize.sm,
    color: colors.textSecondary,
    marginBottom: spacing.md,
  },
  label: {
    fontSize: fontSize.sm,
    fontWeight: '500',
    color: colors.text,
    marginBottom: spacing.xs,
    marginTop: spacing.sm,
  },
  modalInput: {
    backgroundColor: colors.background,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: borderRadius.md,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.md,
    fontSize: fontSize.md,
    color: colors.text,
  },
  modalActions: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    justifyContent: 'flex-end',
    gap: spacing.sm,
    marginTop: spacing.lg,
  },
  modalActionBtn: {
    flexGrow: 1,
    flexBasis: 120,
    minHeight: 44,
    paddingVertical: spacing.sm,
  },
  modalCancelBtn: {
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    borderRadius: borderRadius.md,
    borderWidth: 1,
    borderColor: colors.border,
  },
  modalCancelText: {
    fontSize: fontSize.sm,
    color: colors.textSecondary,
    fontWeight: '500',
  },
  modalConfirmBtn: {
    backgroundColor: colors.primary,
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.sm,
    borderRadius: borderRadius.md,
    minWidth: 100,
    alignItems: 'center',
    justifyContent: 'center',
  },
  modalConfirmText: {
    color: colors.textInverse,
    fontSize: fontSize.sm,
    fontWeight: '600',
  },
});
