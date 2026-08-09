import React, { useCallback, useEffect, useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ActivityIndicator,
  ScrollView,
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
import ConfirmModal from '../components/ConfirmModal';

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
  const [appliedSearch, setAppliedSearch] = useState('');

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

  // Edit medication modal
  const [editVisible, setEditVisible] = useState(false);
  const [editMed, setEditMed] = useState<MedicationWithStock | null>(null);
  const [editName, setEditName] = useState('');
  const [editDosage, setEditDosage] = useState('');
  const [editing, setEditing] = useState(false);

  // Remove medication modal
  const [removeMed, setRemoveMed] = useState<MedicationWithStock | null>(null);

  const fetchStock = useCallback(async () => {
    try {
      setError('');
      const trimmedSearch = search.trim();
      const params: Record<string, string> = {};
      if (trimmedSearch) params.search = trimmedSearch;
      const res = await medicationsApi.stockOverview(params);
      setSections(res.data.sections);
      setAppliedSearch(trimmedSearch);
    } catch {
      setError('Erro ao carregar estoque de medicamentos.');
    }
  }, [search]);

  useEffect(() => {
    // Carrega o estoque apenas na montagem da tela. `fetchStock` muda de
    // identidade a cada tecla digitada no campo de busca (depende de
    // `search`), e reagir a essa mudanca aqui disparava uma nova chamada a
    // API a cada caractere digitado, alem da busca explicita feita em
    // onSubmitEditing/onRefresh.
    const load = async () => {
      setLoading(true);
      await fetchStock();
      setLoading(false);
    };
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

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

  const openEditMedication = (med: MedicationWithStock) => {
    setEditMed(med);
    setEditName(med.name);
    setEditDosage(med.dosage);
    setEditVisible(true);
  };

  const handleEditMedication = async () => {
    if (!editMed || !editName.trim() || !editDosage.trim()) {
      Alert.alert('Erro', 'Preencha nome e dosagem.');
      return;
    }
    setEditing(true);
    try {
      await medicationsApi.update(editMed.id, {
        name: editName.trim(),
        dosage: editDosage.trim(),
      });
      setEditVisible(false);
      setEditMed(null);
      await fetchStock();
    } catch {
      Alert.alert('Erro', 'Nao foi possivel editar o medicamento.');
    } finally {
      setEditing(false);
    }
  };

  const handleRemoveMedication = (med: MedicationWithStock) => {
    setRemoveMed(med);
  };

  const handleConfirmRemoveMedication = async () => {
    if (!removeMed) return;
    const med = removeMed;
    setRemoveMed(null);
    try {
      await medicationsApi.delete(med.id);
      await fetchStock();
    } catch {
      Alert.alert('Erro', 'Nao foi possivel remover o medicamento.');
    }
  };

  // Flatten sections into a single list with section headers
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
          <Text style={styles.medName} numberOfLines={2} ellipsizeMode="tail">
            {med.name}
          </Text>
          <Text style={styles.medDosage} numberOfLines={2} ellipsizeMode="tail">
            {med.dosage}
          </Text>
          {med.next_dose && (
            <Text style={styles.medNextDose} testID={`med-next-dose-${med.id}`}>
              Proxima dose: {med.next_dose.time}
            </Text>
          )}
        </View>
        <View style={styles.medStockContainer}>
          <Text style={[styles.medStock, { color: accent }]}>{med.current_stock}</Text>
          <Text style={styles.medStockLabel}>un.</Text>
        </View>
        <View style={styles.medActions}>
          <TouchableOpacity
            style={[styles.addStockBtn, { borderColor: accent }]}
            onPress={() => openAddStock(med)}
            activeOpacity={0.7}
          >
            <Text style={[styles.addStockBtnText, { color: accent }]}>+ Estoque</Text>
          </TouchableOpacity>
          <TouchableOpacity
            style={styles.iconBtn}
            onPress={() => openEditMedication(med)}
            activeOpacity={0.7}
            testID={`med-edit-${med.id}`}
          >
            <Text style={styles.iconBtnText}>Editar</Text>
          </TouchableOpacity>
          <TouchableOpacity
            style={styles.iconBtn}
            onPress={() => handleRemoveMedication(med)}
            activeOpacity={0.7}
            testID={`med-remove-${med.id}`}
          >
            <Text style={[styles.iconBtnText, styles.removeBtnText]}>Remover</Text>
          </TouchableOpacity>
        </View>
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

      <ScrollView
        contentContainerStyle={styles.listContent}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} colors={[colors.primary]} />
        }
      >
        {flatData.length === 0 ? (
          <View style={styles.emptyContainer}>
            <Text style={styles.emptyText}>
              {error ||
                (appliedSearch
                  ? 'Nenhum resultado encontrado para a busca.'
                  : 'Nenhum medicamento cadastrado.')}
            </Text>
          </View>
        ) : (
          flatData.map((item) => <React.Fragment key={item.key}>{renderItem({ item })}</React.Fragment>)
        )}
      </ScrollView>

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

      {/* Edit Medication Modal */}
      <Modal
        visible={editVisible}
        transparent
        animationType="fade"
        onRequestClose={() => setEditVisible(false)}
      >
        <View style={styles.modalOverlay}>
          <View style={styles.modalCard}>
            <Text style={styles.modalTitle}>Editar Medicamento</Text>
            <Text style={styles.label}>Nome</Text>
            <TextInput
              style={styles.modalInput}
              value={editName}
              onChangeText={setEditName}
              placeholder="Ex: Paracetamol"
              placeholderTextColor={colors.textMuted}
              autoFocus
            />
            <Text style={styles.label}>Dosagem</Text>
            <TextInput
              style={styles.modalInput}
              value={editDosage}
              onChangeText={setEditDosage}
              placeholder="Ex: 500mg"
              placeholderTextColor={colors.textMuted}
            />
            <View style={styles.modalActions}>
              <TouchableOpacity
                style={styles.modalCancelBtn}
                onPress={() => setEditVisible(false)}
              >
                <Text style={styles.modalCancelText}>Cancelar</Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={[styles.modalConfirmBtn, editing && { backgroundColor: colors.primaryLight }]}
                onPress={handleEditMedication}
                disabled={editing}
                testID="med-edit-confirm"
              >
                {editing ? (
                  <ActivityIndicator color={colors.textInverse} size="small" />
                ) : (
                  <Text style={styles.modalConfirmText}>Salvar</Text>
                )}
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>

      <ConfirmModal
        visible={removeMed !== null}
        title="Confirma a remocao?"
        message={`Deseja remover ${removeMed?.name}?`}
        confirmText="Remover"
        destructive
        onConfirm={handleConfirmRemoveMedication}
        onCancel={() => setRemoveMed(null)}
      />
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
    flexShrink: 1,
    minWidth: 0,
  },
  medName: {
    fontSize: fontSize.md,
    fontWeight: '600',
    color: colors.text,
    flexShrink: 1,
    flexWrap: 'wrap',
  },
  medDosage: {
    fontSize: fontSize.sm,
    color: colors.textSecondary,
    marginTop: 2,
    flexShrink: 1,
    flexWrap: 'wrap',
  },
  medNextDose: {
    fontSize: fontSize.xs,
    color: colors.textMuted,
    marginTop: 2,
  },
  medStockContainer: {
    alignItems: 'center',
    marginHorizontal: spacing.sm,
    flexShrink: 0,
  },
  medStock: {
    fontSize: fontSize.xl,
    fontWeight: '700',
  },
  medStockLabel: {
    fontSize: fontSize.xs,
    color: colors.textMuted,
  },
  medActions: {
    alignItems: 'flex-end',
    gap: spacing.xs,
    flexShrink: 0,
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
  iconBtn: {
    paddingHorizontal: spacing.sm,
    paddingVertical: spacing.xs,
  },
  iconBtnText: {
    fontSize: fontSize.xs,
    fontWeight: '600',
    color: colors.textSecondary,
  },
  removeBtnText: {
    color: colors.stockDanger,
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
