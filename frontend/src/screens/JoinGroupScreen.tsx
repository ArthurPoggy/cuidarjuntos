import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  StyleSheet,
  ActivityIndicator,
  KeyboardAvoidingView,
  Platform,
  ScrollView,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useAuth } from '../contexts/AuthContext';
import { groupsApi } from '../api/endpoints';
import { colors, spacing, fontSize, borderRadius } from '../theme';
import { RelationToPatient } from '../types/models';
import type { CareGroup } from '../types/models';
import type { AxiosError } from 'axios';

interface FieldErrors {
  [key: string]: string[];
}

const RELATION_OPTIONS: { label: string; value: string }[] = [
  { label: 'Selecione sua relacao...', value: '' },
  { label: 'Eu mesmo (paciente)', value: RelationToPatient.SELF },
  { label: 'Familiar', value: RelationToPatient.FAMILY },
  { label: 'Medico', value: RelationToPatient.DOCTOR },
  { label: 'Cuidador', value: RelationToPatient.CAREGIVER },
  { label: 'Outro', value: RelationToPatient.OTHER },
];

export default function JoinGroupScreen() {
  const { refreshGroup } = useAuth();

  const [groups, setGroups] = useState<CareGroup[]>([]);
  const [selectedGroupId, setSelectedGroupId] = useState<number | null>(null);
  const [relation, setRelation] = useState('');
  const [pin, setPin] = useState('');
  const [loading, setLoading] = useState(false);
  const [fetchingGroups, setFetchingGroups] = useState(true);
  const [error, setError] = useState('');
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});
  const [showGroupPicker, setShowGroupPicker] = useState(false);
  const [showRelationPicker, setShowRelationPicker] = useState(false);

  useEffect(() => {
    fetchGroups();
  }, []);

  const fetchGroups = async () => {
    setFetchingGroups(true);
    try {
      const { data } = await groupsApi.list();
      setGroups(data);
    } catch {
      setError('Nao foi possivel carregar os grupos. Tente novamente.');
    } finally {
      setFetchingGroups(false);
    }
  };

  const getFieldError = (field: string): string | null => {
    if (fieldErrors[field] && fieldErrors[field].length > 0) {
      return fieldErrors[field].join(' ');
    }
    return null;
  };

  const getSelectedGroupLabel = (): string => {
    if (selectedGroupId === null) return 'Selecione um grupo...';
    const found = groups.find((g) => g.id === selectedGroupId);
    return found ? `${found.name} (${found.patient.name})` : 'Selecione um grupo...';
  };

  const getRelationLabel = (): string => {
    const found = RELATION_OPTIONS.find((opt) => opt.value === relation);
    return found ? found.label : 'Selecione sua relacao...';
  };

  const handleJoin = async () => {
    setError('');
    setFieldErrors({});

    if (selectedGroupId === null || !relation || !pin.trim()) {
      setError('Preencha todos os campos obrigatorios.');
      return;
    }

    if (pin.length !== 4 || !/^\d{4}$/.test(pin)) {
      setFieldErrors({ pin: ['O PIN deve conter exatamente 4 digitos numericos.'] });
      return;
    }

    setLoading(true);

    try {
      await groupsApi.join({
        group_id: selectedGroupId,
        relation_to_patient: relation,
        pin,
      });
      await refreshGroup();
    } catch (err) {
      const axiosErr = err as AxiosError<FieldErrors & { detail?: string; non_field_errors?: string[] }>;
      if (axiosErr.response?.data) {
        const data = axiosErr.response.data;
        if (data.detail) {
          setError(data.detail);
        } else if (data.non_field_errors) {
          setError(data.non_field_errors.join(' '));
        } else {
          const errors: FieldErrors = {};
          Object.entries(data).forEach(([key, val]) => {
            if (Array.isArray(val)) {
              errors[key] = val as string[];
            }
          });
          if (Object.keys(errors).length > 0) {
            setFieldErrors(errors);
          } else {
            setError('Erro ao entrar no grupo. Verifique o PIN e tente novamente.');
          }
        }
      } else {
        setError('Erro de conexao. Verifique sua internet.');
      }
    } finally {
      setLoading(false);
    }
  };

  if (fetchingGroups) {
    return (
      <SafeAreaView style={styles.safe}>
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color={colors.primary} />
          <Text style={styles.loadingText}>Carregando grupos...</Text>
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.safe}>
      <KeyboardAvoidingView
        style={styles.flex}
        behavior={Platform.OS === 'ios' ? 'padding' : undefined}
      >
        <ScrollView
          contentContainerStyle={styles.scrollContent}
          keyboardShouldPersistTaps="handled"
        >
          <View style={styles.card}>
            <Text style={styles.cardTitle}>Entrar em um Grupo</Text>

            {error !== '' && (
              <View style={styles.errorBox}>
                <Text style={styles.errorText}>{error}</Text>
              </View>
            )}

            {groups.length === 0 ? (
              <View style={styles.emptyBox}>
                <Text style={styles.emptyTitle}>Nenhum grupo encontrado</Text>
                <Text style={styles.emptyText}>
                  No momento nao existem grupos disponiveis. Peca ao administrador do grupo para
                  criar um grupo primeiro.
                </Text>
                <TouchableOpacity
                  style={styles.retryButton}
                  onPress={fetchGroups}
                  activeOpacity={0.7}
                >
                  <Text style={styles.retryText}>Tentar Novamente</Text>
                </TouchableOpacity>
              </View>
            ) : (
              <>
                <Text style={styles.label}>Grupo *</Text>
                <TouchableOpacity
                  style={[styles.pickerButton, getFieldError('group_id') && styles.inputError]}
                  onPress={() => {
                    setShowGroupPicker(!showGroupPicker);
                    setShowRelationPicker(false);
                  }}
                  disabled={loading}
                >
                  <Text
                    style={[
                      styles.pickerButtonText,
                      selectedGroupId === null && styles.pickerPlaceholder,
                    ]}
                  >
                    {getSelectedGroupLabel()}
                  </Text>
                  <Text style={styles.pickerArrow}>{showGroupPicker ? '\u25B2' : '\u25BC'}</Text>
                </TouchableOpacity>
                {showGroupPicker && (
                  <View style={styles.pickerDropdown}>
                    {groups.map((group) => (
                      <TouchableOpacity
                        key={group.id}
                        style={[
                          styles.pickerOption,
                          selectedGroupId === group.id && styles.pickerOptionSelected,
                        ]}
                        onPress={() => {
                          setSelectedGroupId(group.id);
                          setShowGroupPicker(false);
                        }}
                      >
                        <Text
                          style={[
                            styles.pickerOptionText,
                            selectedGroupId === group.id && styles.pickerOptionTextSelected,
                          ]}
                        >
                          {group.name}
                        </Text>
                        <Text style={styles.pickerOptionSubtext}>
                          Paciente: {group.patient.name} - {group.member_count} membro(s)
                        </Text>
                      </TouchableOpacity>
                    ))}
                  </View>
                )}
                {getFieldError('group_id') && (
                  <Text style={styles.fieldError}>{getFieldError('group_id')}</Text>
                )}

                <Text style={styles.label}>Sua Relacao com o Paciente *</Text>
                <TouchableOpacity
                  style={[
                    styles.pickerButton,
                    getFieldError('relation_to_patient') && styles.inputError,
                  ]}
                  onPress={() => {
                    setShowRelationPicker(!showRelationPicker);
                    setShowGroupPicker(false);
                  }}
                  disabled={loading}
                >
                  <Text
                    style={[styles.pickerButtonText, !relation && styles.pickerPlaceholder]}
                  >
                    {getRelationLabel()}
                  </Text>
                  <Text style={styles.pickerArrow}>
                    {showRelationPicker ? '\u25B2' : '\u25BC'}
                  </Text>
                </TouchableOpacity>
                {showRelationPicker && (
                  <View style={styles.pickerDropdown}>
                    {RELATION_OPTIONS.filter((opt) => opt.value !== '').map((opt) => (
                      <TouchableOpacity
                        key={opt.value}
                        style={[
                          styles.pickerOption,
                          relation === opt.value && styles.pickerOptionSelected,
                        ]}
                        onPress={() => {
                          setRelation(opt.value);
                          setShowRelationPicker(false);
                        }}
                      >
                        <Text
                          style={[
                            styles.pickerOptionText,
                            relation === opt.value && styles.pickerOptionTextSelected,
                          ]}
                        >
                          {opt.label}
                        </Text>
                      </TouchableOpacity>
                    ))}
                  </View>
                )}
                {getFieldError('relation_to_patient') && (
                  <Text style={styles.fieldError}>{getFieldError('relation_to_patient')}</Text>
                )}

                <Text style={styles.label}>PIN do Grupo (4 digitos) *</Text>
                <TextInput
                  style={[styles.input, getFieldError('pin') && styles.inputError]}
                  placeholder="Digite o PIN de 4 digitos"
                  placeholderTextColor={colors.textMuted}
                  keyboardType="numeric"
                  maxLength={4}
                  secureTextEntry
                  value={pin}
                  onChangeText={setPin}
                  editable={!loading}
                />
                {getFieldError('pin') && (
                  <Text style={styles.fieldError}>{getFieldError('pin')}</Text>
                )}

                <TouchableOpacity
                  style={[styles.button, loading && styles.buttonDisabled]}
                  onPress={handleJoin}
                  disabled={loading}
                  activeOpacity={0.8}
                >
                  {loading ? (
                    <ActivityIndicator color={colors.textInverse} />
                  ) : (
                    <Text style={styles.buttonText}>Entrar no Grupo</Text>
                  )}
                </TouchableOpacity>
              </>
            )}
          </View>
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: {
    flex: 1,
    backgroundColor: colors.background,
  },
  flex: {
    flex: 1,
  },
  scrollContent: {
    flexGrow: 1,
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.lg,
  },
  loadingContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  loadingText: {
    marginTop: spacing.md,
    fontSize: fontSize.md,
    color: colors.textSecondary,
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
  },
  cardTitle: {
    fontSize: fontSize.xl,
    fontWeight: '600',
    color: colors.text,
    marginBottom: spacing.lg,
    textAlign: 'center',
  },
  errorBox: {
    backgroundColor: '#FEF2F2',
    borderWidth: 1,
    borderColor: '#FECACA',
    borderRadius: borderRadius.sm,
    padding: spacing.md,
    marginBottom: spacing.md,
  },
  errorText: {
    color: colors.danger,
    fontSize: fontSize.sm,
    textAlign: 'center',
  },
  emptyBox: {
    alignItems: 'center',
    paddingVertical: spacing.lg,
  },
  emptyTitle: {
    fontSize: fontSize.lg,
    fontWeight: '600',
    color: colors.text,
    marginBottom: spacing.sm,
  },
  emptyText: {
    fontSize: fontSize.sm,
    color: colors.textSecondary,
    textAlign: 'center',
    lineHeight: 20,
    marginBottom: spacing.lg,
  },
  retryButton: {
    borderWidth: 1,
    borderColor: colors.primary,
    borderRadius: borderRadius.md,
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.sm,
  },
  retryText: {
    color: colors.primary,
    fontSize: fontSize.md,
    fontWeight: '500',
  },
  label: {
    fontSize: fontSize.sm,
    fontWeight: '500',
    color: colors.text,
    marginBottom: spacing.xs,
    marginTop: spacing.md,
  },
  input: {
    backgroundColor: colors.background,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: borderRadius.md,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.md,
    fontSize: fontSize.md,
    color: colors.text,
  },
  inputError: {
    borderColor: colors.danger,
  },
  fieldError: {
    color: colors.danger,
    fontSize: fontSize.xs,
    marginTop: spacing.xs,
  },
  pickerButton: {
    backgroundColor: colors.background,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: borderRadius.md,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.md,
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  pickerButtonText: {
    fontSize: fontSize.md,
    color: colors.text,
    flex: 1,
  },
  pickerPlaceholder: {
    color: colors.textMuted,
  },
  pickerArrow: {
    fontSize: fontSize.xs,
    color: colors.textMuted,
    marginLeft: spacing.sm,
  },
  pickerDropdown: {
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: borderRadius.md,
    marginTop: spacing.xs,
    overflow: 'hidden',
  },
  pickerOption: {
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.md,
    borderBottomWidth: 1,
    borderBottomColor: colors.borderLight,
  },
  pickerOptionSelected: {
    backgroundColor: colors.primaryLight + '30',
  },
  pickerOptionText: {
    fontSize: fontSize.md,
    color: colors.text,
  },
  pickerOptionTextSelected: {
    color: colors.primary,
    fontWeight: '600',
  },
  pickerOptionSubtext: {
    fontSize: fontSize.xs,
    color: colors.textSecondary,
    marginTop: spacing.xs,
  },
  button: {
    backgroundColor: colors.primary,
    borderRadius: borderRadius.md,
    paddingVertical: spacing.md,
    alignItems: 'center',
    justifyContent: 'center',
    marginTop: spacing.xl,
    minHeight: 50,
  },
  buttonDisabled: {
    backgroundColor: colors.primaryLight,
  },
  buttonText: {
    color: colors.textInverse,
    fontSize: fontSize.lg,
    fontWeight: '600',
  },
});
