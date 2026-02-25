import React, { useState } from 'react';
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

export default function CreateGroupScreen() {
  const { refreshGroup } = useAuth();

  const [groupName, setGroupName] = useState('');
  const [patientName, setPatientName] = useState('');
  const [patientBirthDate, setPatientBirthDate] = useState('');
  const [relation, setRelation] = useState('');
  const [healthData, setHealthData] = useState('');
  const [groupPin, setGroupPin] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});
  const [showRelationPicker, setShowRelationPicker] = useState(false);

  const formatDateInput = (value: string): string => {
    const digits = value.replace(/\D/g, '').slice(0, 8);
    if (digits.length <= 2) return digits;
    if (digits.length <= 4) return `${digits.slice(0, 2)}/${digits.slice(2)}`;
    return `${digits.slice(0, 2)}/${digits.slice(2, 4)}/${digits.slice(4)}`;
  };

  const handleBirthDateChange = (value: string) => {
    setPatientBirthDate(formatDateInput(value));
  };

  const parseDateToISO = (dateStr: string): string | undefined => {
    if (!dateStr.trim()) return undefined;
    const parts = dateStr.split('/');
    if (parts.length !== 3) return undefined;
    const [day, month, year] = parts;
    if (day.length !== 2 || month.length !== 2 || year.length !== 4) return undefined;
    return `${year}-${month}-${day}`;
  };

  const getFieldError = (field: string): string | null => {
    if (fieldErrors[field] && fieldErrors[field].length > 0) {
      return fieldErrors[field].join(' ');
    }
    return null;
  };

  const getRelationLabel = (): string => {
    const found = RELATION_OPTIONS.find((opt) => opt.value === relation);
    return found ? found.label : 'Selecione sua relacao...';
  };

  const handleCreate = async () => {
    setError('');
    setFieldErrors({});

    if (!groupName.trim() || !patientName.trim() || !relation || !groupPin.trim()) {
      setError('Preencha todos os campos obrigatorios.');
      return;
    }

    if (groupPin.length !== 4 || !/^\d{4}$/.test(groupPin)) {
      setFieldErrors({ group_pin: ['O PIN deve conter exatamente 4 digitos numericos.'] });
      return;
    }

    const isoDate = parseDateToISO(patientBirthDate);

    setLoading(true);

    try {
      await groupsApi.create({
        group_name: groupName.trim(),
        patient_name: patientName.trim(),
        patient_birth_date: isoDate,
        relation_to_patient: relation,
        health_data: healthData.trim() || undefined,
        group_pin: groupPin,
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
            setError('Erro ao criar grupo. Tente novamente.');
          }
        }
      } else {
        setError('Erro de conexao. Verifique sua internet.');
      }
    } finally {
      setLoading(false);
    }
  };

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
            <Text style={styles.cardTitle}>Novo Grupo de Cuidado</Text>

            {error !== '' && (
              <View style={styles.errorBox}>
                <Text style={styles.errorText}>{error}</Text>
              </View>
            )}

            <Text style={styles.sectionTitle}>Dados do Grupo</Text>

            <Text style={styles.label}>Nome do Grupo *</Text>
            <TextInput
              style={[styles.input, getFieldError('group_name') && styles.inputError]}
              placeholder="Ex: Cuidado da Vovo Maria"
              placeholderTextColor={colors.textMuted}
              value={groupName}
              onChangeText={setGroupName}
              editable={!loading}
            />
            {getFieldError('group_name') && (
              <Text style={styles.fieldError}>{getFieldError('group_name')}</Text>
            )}

            <Text style={styles.label}>PIN do Grupo (4 digitos) *</Text>
            <TextInput
              style={[styles.input, getFieldError('group_pin') && styles.inputError]}
              placeholder="Ex: 1234"
              placeholderTextColor={colors.textMuted}
              keyboardType="numeric"
              maxLength={4}
              value={groupPin}
              onChangeText={setGroupPin}
              editable={!loading}
            />
            {getFieldError('group_pin') && (
              <Text style={styles.fieldError}>{getFieldError('group_pin')}</Text>
            )}

            <View style={styles.divider} />
            <Text style={styles.sectionTitle}>Dados do Paciente</Text>

            <Text style={styles.label}>Nome do Paciente *</Text>
            <TextInput
              style={[styles.input, getFieldError('patient_name') && styles.inputError]}
              placeholder="Nome completo do paciente"
              placeholderTextColor={colors.textMuted}
              value={patientName}
              onChangeText={setPatientName}
              editable={!loading}
            />
            {getFieldError('patient_name') && (
              <Text style={styles.fieldError}>{getFieldError('patient_name')}</Text>
            )}

            <Text style={styles.label}>Data de Nascimento do Paciente</Text>
            <TextInput
              style={[styles.input, getFieldError('patient_birth_date') && styles.inputError]}
              placeholder="DD/MM/AAAA"
              placeholderTextColor={colors.textMuted}
              keyboardType="numeric"
              value={patientBirthDate}
              onChangeText={handleBirthDateChange}
              editable={!loading}
              maxLength={10}
            />
            {getFieldError('patient_birth_date') && (
              <Text style={styles.fieldError}>{getFieldError('patient_birth_date')}</Text>
            )}

            <Text style={styles.label}>Sua Relacao com o Paciente *</Text>
            <TouchableOpacity
              style={[styles.pickerButton, getFieldError('relation_to_patient') && styles.inputError]}
              onPress={() => setShowRelationPicker(!showRelationPicker)}
              disabled={loading}
            >
              <Text
                style={[styles.pickerButtonText, !relation && styles.pickerPlaceholder]}
              >
                {getRelationLabel()}
              </Text>
              <Text style={styles.pickerArrow}>{showRelationPicker ? '\u25B2' : '\u25BC'}</Text>
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

            <Text style={styles.label}>Dados de Saude (opcional)</Text>
            <TextInput
              style={[styles.input, styles.textArea, getFieldError('health_data') && styles.inputError]}
              placeholder="Condicoes de saude, alergias, observacoes..."
              placeholderTextColor={colors.textMuted}
              multiline
              numberOfLines={4}
              textAlignVertical="top"
              value={healthData}
              onChangeText={setHealthData}
              editable={!loading}
            />
            {getFieldError('health_data') && (
              <Text style={styles.fieldError}>{getFieldError('health_data')}</Text>
            )}

            <TouchableOpacity
              style={[styles.button, loading && styles.buttonDisabled]}
              onPress={handleCreate}
              disabled={loading}
              activeOpacity={0.8}
            >
              {loading ? (
                <ActivityIndicator color={colors.textInverse} />
              ) : (
                <Text style={styles.buttonText}>Criar Grupo</Text>
              )}
            </TouchableOpacity>
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
  sectionTitle: {
    fontSize: fontSize.md,
    fontWeight: '600',
    color: colors.primary,
    marginBottom: spacing.sm,
    marginTop: spacing.xs,
  },
  divider: {
    height: 1,
    backgroundColor: colors.divider,
    marginVertical: spacing.lg,
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
  textArea: {
    minHeight: 100,
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
