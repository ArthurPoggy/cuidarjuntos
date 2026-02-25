import React, { useState, useEffect, useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ActivityIndicator,
  ScrollView,
  TouchableOpacity,
  TextInput,
  Switch,
  Alert,
  Platform,
  KeyboardAvoidingView,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useNavigation, useRoute } from '@react-navigation/native';
import { useForm, Controller } from 'react-hook-form';
import { recordsApi, medicationsApi } from '../api/endpoints';
import { colors, spacing, fontSize, borderRadius } from '../theme';
import {
  CATEGORY_META,
  RECORD_TYPES,
  VITAL_KIND_CHOICES,
  VITAL_STATUS_CHOICES,
  BATHROOM_TYPE_CHOICES,
  MEAL_TYPE_CHOICES,
  MEAL_ACCEPTANCE_CHOICES,
  SLEEP_EVENT_CHOICES,
  OTHER_VALUE,
} from '../utils/constants';
import { RecordType, Recurrence, ProgressTrend } from '../types/models';
import type { Medication } from '../types/models';
import DateTimePicker from '../components/DateTimePicker';

const RECURRENCE_OPTIONS = [
  { value: Recurrence.NONE, label: 'Sem repetição' },
  { value: Recurrence.DAILY, label: 'Diária' },
  { value: Recurrence.WEEKLY, label: 'Semanal' },
  { value: Recurrence.MONTHLY, label: 'Mensal' },
];

const PROGRESS_TREND_OPTIONS = [
  { value: ProgressTrend.EVOLUTION, label: 'Evolução' },
  { value: ProgressTrend.REGRESSION, label: 'Regressão' },
  { value: OTHER_VALUE, label: 'Outro' },
];

interface FormData {
  type: string;
  what: string;
  description: string;
  // Medication
  medication: string;
  medication_other: string;
  capsule_quantity: string;
  // Vital
  vital_kind: string;
  vital_kind_other: string;
  vital_status: string;
  vital_status_other: string;
  // Bathroom
  bathroom_type: string;
  bathroom_type_other: string;
  bathroom_no_occurrence: boolean;
  // Meal
  meal_type: string;
  meal_type_other: string;
  meal_acceptance: string;
  meal_acceptance_other: string;
  // Sleep
  sleep_event: string;
  sleep_event_other: string;
  // Progress
  progress_trend: string;
  progress_trend_other: string;
  // Common
  date: Date;
  time: Date;
  is_exception: boolean;
  recurrence: string;
  repeat_until: Date | null;
}

function parseDateString(dateStr: string): Date {
  const [y, m, d] = dateStr.split('-').map(Number);
  return new Date(y, m - 1, d);
}

function parseTimeString(timeStr: string): Date {
  const [h, m] = timeStr.split(':').map(Number);
  const date = new Date();
  date.setHours(h, m, 0, 0);
  return date;
}

function formatDateToAPI(date: Date): string {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, '0');
  const d = String(date.getDate()).padStart(2, '0');
  return `${y}-${m}-${d}`;
}

function formatTimeToAPI(time: Date): string {
  const h = String(time.getHours()).padStart(2, '0');
  const m = String(time.getMinutes()).padStart(2, '0');
  return `${h}:${m}`;
}

export default function RecordCreateScreen() {
  const navigation = useNavigation<any>();
  const route = useRoute<any>();
  const editData = route.params?.record ?? null;

  const [step, setStep] = useState(editData ? 2 : 1);
  const [submitting, setSubmitting] = useState(false);
  const [medications, setMedications] = useState<Medication[]>([]);
  const [loadingMeds, setLoadingMeds] = useState(false);

  const { control, handleSubmit, watch, setValue } = useForm<FormData>({
    defaultValues: {
      type: editData?.type ?? '',
      what: editData?.what ?? '',
      description: editData?.description ?? '',
      medication: editData?.medication ? String(editData.medication) : '',
      medication_other: '',
      capsule_quantity: editData?.capsule_quantity ? String(editData.capsule_quantity) : '1',
      vital_kind: '',
      vital_kind_other: '',
      vital_status: '',
      vital_status_other: '',
      bathroom_type: '',
      bathroom_type_other: '',
      bathroom_no_occurrence: false,
      meal_type: '',
      meal_type_other: '',
      meal_acceptance: '',
      meal_acceptance_other: '',
      sleep_event: '',
      sleep_event_other: '',
      progress_trend: editData?.progress_trend ?? '',
      progress_trend_other: '',
      date: editData?.date ? parseDateString(editData.date) : new Date(),
      time: editData?.time ? parseTimeString(editData.time) : new Date(),
      is_exception: editData?.is_exception ?? false,
      recurrence: editData?.recurrence ?? Recurrence.NONE,
      repeat_until: editData?.repeat_until ? parseDateString(editData.repeat_until) : null,
    },
  });

  const selectedType = watch('type');
  const selectedRecurrence = watch('recurrence');

  // Fetch medications when type is medication
  const fetchMedications = useCallback(async () => {
    setLoadingMeds(true);
    try {
      const { data } = await medicationsApi.list({ page_size: '200' });
      setMedications(data.results ?? []);
    } catch {
      setMedications([]);
    } finally {
      setLoadingMeds(false);
    }
  }, []);

  useEffect(() => {
    if (selectedType === RecordType.MEDICATION) {
      fetchMedications();
    }
  }, [selectedType, fetchMedications]);

  // Pre-fill sub-fields when editing
  useEffect(() => {
    if (!editData) return;
    const what = editData.what || '';
    const parts = what.split('•').map((s: string) => s.trim());

    if (editData.type === RecordType.VITAL && parts.length >= 1) {
      const kindChoices = VITAL_KIND_CHOICES.filter(c => c !== OTHER_VALUE);
      if (kindChoices.includes(parts[0])) {
        setValue('vital_kind', parts[0]);
      } else {
        setValue('vital_kind', OTHER_VALUE);
        setValue('vital_kind_other', parts[0]);
      }
      if (parts[1]) {
        const statusChoices = VITAL_STATUS_CHOICES.filter(c => c !== OTHER_VALUE);
        if (statusChoices.includes(parts[1])) {
          setValue('vital_status', parts[1]);
        } else {
          setValue('vital_status', OTHER_VALUE);
          setValue('vital_status_other', parts[1]);
        }
      }
    }
    if (editData.type === RecordType.MEAL && parts.length >= 1) {
      const mealChoices = MEAL_TYPE_CHOICES.filter(c => c !== OTHER_VALUE);
      if (mealChoices.includes(parts[0])) {
        setValue('meal_type', parts[0]);
      } else {
        setValue('meal_type', OTHER_VALUE);
        setValue('meal_type_other', parts[0]);
      }
      if (parts[1]) {
        const accChoices = MEAL_ACCEPTANCE_CHOICES.filter(c => c !== OTHER_VALUE);
        if (accChoices.includes(parts[1])) {
          setValue('meal_acceptance', parts[1]);
        } else {
          setValue('meal_acceptance', OTHER_VALUE);
          setValue('meal_acceptance_other', parts[1]);
        }
      }
    }
    if (editData.type === RecordType.BATHROOM) {
      if (what.toLowerCase() === 'sem ocorrência') {
        setValue('bathroom_no_occurrence', true);
      } else {
        const bathChoices = BATHROOM_TYPE_CHOICES.filter(c => c !== OTHER_VALUE);
        if (bathChoices.includes(what)) {
          setValue('bathroom_type', what);
        } else {
          setValue('bathroom_type', OTHER_VALUE);
          setValue('bathroom_type_other', what);
        }
      }
    }
    if (editData.type === RecordType.SLEEP) {
      const norm = what.toLowerCase();
      if (norm === 'dormiu' || norm === 'acordou') {
        setValue('sleep_event', norm);
      } else {
        setValue('sleep_event', OTHER_VALUE);
        setValue('sleep_event_other', what);
      }
    }
    if (editData.type === RecordType.MEDICATION && !editData.medication) {
      setValue('medication', OTHER_VALUE);
      setValue('medication_other', what);
    }
  }, [editData, setValue]);

  const handleTypeSelect = (type: string) => {
    setValue('type', type);
    setStep(2);
  };

  const onSubmit = async (formData: FormData) => {
    setSubmitting(true);
    try {
      const payload: Record<string, unknown> = {
        type: formData.type,
        description: formData.description,
        date: formatDateToAPI(formData.date),
        time: formatTimeToAPI(formData.time),
        is_exception: formData.is_exception,
        recurrence: formData.recurrence,
      };

      if (formData.recurrence !== Recurrence.NONE && formData.repeat_until) {
        payload.repeat_until = formatDateToAPI(formData.repeat_until);
      }

      // Build "what" and type-specific fields
      switch (formData.type) {
        case RecordType.MEDICATION: {
          const med = formData.medication;
          if (med && med !== OTHER_VALUE) {
            payload.medication = Number(med);
            const found = medications.find(m => m.id === Number(med));
            payload.what = found ? `${found.name} ${found.dosage}`.trim() : '';
          } else {
            payload.what = formData.medication_other.trim();
          }
          payload.capsule_quantity = Number(formData.capsule_quantity) || 1;
          break;
        }
        case RecordType.VITAL: {
          const kind = formData.vital_kind === OTHER_VALUE
            ? formData.vital_kind_other.trim()
            : formData.vital_kind;
          const status = formData.vital_status === OTHER_VALUE
            ? formData.vital_status_other.trim()
            : formData.vital_status;
          payload.vital_kind = kind;
          payload.vital_status = status;
          payload.what = [kind, status].filter(Boolean).join(' • ');
          break;
        }
        case RecordType.BATHROOM: {
          if (formData.bathroom_no_occurrence) {
            payload.what = 'Sem ocorrência';
            payload.bathroom_no_occurrence = true;
          } else {
            const btype = formData.bathroom_type === OTHER_VALUE
              ? formData.bathroom_type_other.trim()
              : formData.bathroom_type;
            payload.bathroom_type = btype;
            payload.what = btype;
          }
          break;
        }
        case RecordType.MEAL: {
          const meal = formData.meal_type === OTHER_VALUE
            ? formData.meal_type_other.trim()
            : formData.meal_type;
          const acceptance = formData.meal_acceptance === OTHER_VALUE
            ? formData.meal_acceptance_other.trim()
            : formData.meal_acceptance;
          payload.meal_type = meal;
          payload.meal_acceptance = acceptance;
          payload.what = [meal, acceptance].filter(Boolean).join(' • ');
          break;
        }
        case RecordType.SLEEP: {
          const sleepVal = formData.sleep_event === OTHER_VALUE
            ? formData.sleep_event_other.trim()
            : formData.sleep_event;
          payload.sleep_event = sleepVal;
          payload.what = sleepVal;
          break;
        }
        case RecordType.PROGRESS: {
          const ptVal = formData.progress_trend === OTHER_VALUE
            ? formData.progress_trend_other.trim()
            : formData.progress_trend;
          payload.progress_trend = ptVal;
          payload.what = '';
          break;
        }
        default: {
          payload.what = formData.what;
          break;
        }
      }

      if (editData?.id) {
        await recordsApi.update(editData.id, payload);
      } else {
        await recordsApi.create(payload);
      }

      navigation.goBack();
    } catch (err: any) {
      const detail = err?.response?.data;
      const msg = detail
        ? typeof detail === 'string' ? detail : JSON.stringify(detail)
        : 'Não foi possível salvar o registro.';
      Alert.alert('Erro', msg);
    } finally {
      setSubmitting(false);
    }
  };

  // ----- Render Helpers -----

  const renderRadioOptions = (
    options: string[],
    fieldName: keyof FormData,
    otherFieldName?: keyof FormData,
  ) => {
    const currentValue = watch(fieldName) as string;
    const isOtherSelected = currentValue === OTHER_VALUE;

    return (
      <View>
        <Controller
          control={control}
          name={fieldName}
          render={({ field: { value, onChange } }) => (
            <View style={styles.pickerRow}>
              {options.map((opt) => {
                const label = opt === OTHER_VALUE ? 'Outro' : opt;
                return (
                  <TouchableOpacity
                    key={opt}
                    style={[
                      styles.pickerOption,
                      value === opt && styles.pickerOptionActive,
                    ]}
                    onPress={() => onChange(opt)}
                  >
                    <Text
                      style={[
                        styles.pickerOptionText,
                        value === opt && styles.pickerOptionTextActive,
                      ]}
                    >
                      {label}
                    </Text>
                  </TouchableOpacity>
                );
              })}
            </View>
          )}
        />
        {isOtherSelected && otherFieldName && (
          <Controller
            control={control}
            name={otherFieldName}
            render={({ field: { value, onChange } }) => (
              <TextInput
                style={[styles.input, { marginTop: spacing.sm }]}
                value={value as string}
                onChangeText={onChange}
                placeholder="Especifique..."
                placeholderTextColor={colors.textMuted}
              />
            )}
          />
        )}
      </View>
    );
  };

  const renderTypeSpecificFields = () => {
    switch (selectedType) {
      case RecordType.MEDICATION:
        return (
          <View>
            <Text style={styles.label}>Remédio / Dose</Text>
            {loadingMeds ? (
              <ActivityIndicator size="small" color={colors.primary} style={{ marginVertical: spacing.md }} />
            ) : (
              <Controller
                control={control}
                name="medication"
                render={({ field: { value, onChange } }) => (
                  <View style={styles.pickerRow}>
                    {medications.map((med) => (
                      <TouchableOpacity
                        key={String(med.id)}
                        style={[
                          styles.pickerOption,
                          value === String(med.id) && styles.pickerOptionActive,
                        ]}
                        onPress={() => onChange(String(med.id))}
                      >
                        <Text
                          style={[
                            styles.pickerOptionText,
                            value === String(med.id) && styles.pickerOptionTextActive,
                          ]}
                        >
                          {med.name} {med.dosage}
                        </Text>
                      </TouchableOpacity>
                    ))}
                    <TouchableOpacity
                      style={[
                        styles.pickerOption,
                        value === OTHER_VALUE && styles.pickerOptionActive,
                      ]}
                      onPress={() => onChange(OTHER_VALUE)}
                    >
                      <Text
                        style={[
                          styles.pickerOptionText,
                          value === OTHER_VALUE && styles.pickerOptionTextActive,
                        ]}
                      >
                        Outro
                      </Text>
                    </TouchableOpacity>
                  </View>
                )}
              />
            )}
            {watch('medication') === OTHER_VALUE && (
              <>
                <Text style={styles.label}>Outro medicamento/dose</Text>
                <Controller
                  control={control}
                  name="medication_other"
                  render={({ field: { value, onChange } }) => (
                    <TextInput
                      style={styles.input}
                      value={value}
                      onChangeText={onChange}
                      placeholder="Nome e dose"
                      placeholderTextColor={colors.textMuted}
                    />
                  )}
                />
              </>
            )}
            <Text style={styles.label}>Quantidade de cápsulas/gotas</Text>
            <Controller
              control={control}
              name="capsule_quantity"
              render={({ field: { value, onChange } }) => (
                <TextInput
                  style={styles.input}
                  value={value}
                  onChangeText={onChange}
                  placeholder="1"
                  placeholderTextColor={colors.textMuted}
                  keyboardType="numeric"
                />
              )}
            />
          </View>
        );

      case RecordType.VITAL:
        return (
          <View>
            <Text style={styles.label}>Qual</Text>
            {renderRadioOptions(VITAL_KIND_CHOICES, 'vital_kind', 'vital_kind_other')}
            <Text style={styles.label}>Status</Text>
            {renderRadioOptions(VITAL_STATUS_CHOICES, 'vital_status', 'vital_status_other')}
          </View>
        );

      case RecordType.BATHROOM:
        return (
          <View>
            <Text style={styles.label}>Tipo</Text>
            {renderRadioOptions(BATHROOM_TYPE_CHOICES, 'bathroom_type', 'bathroom_type_other')}
            <View style={styles.switchRow}>
              <Text style={styles.switchLabel}>Sem ocorrência durante o dia</Text>
              <Controller
                control={control}
                name="bathroom_no_occurrence"
                render={({ field: { value, onChange } }) => (
                  <Switch
                    value={value}
                    onValueChange={onChange}
                    trackColor={{ false: colors.border, true: colors.primaryLight }}
                    thumbColor={value ? colors.primary : colors.textMuted}
                  />
                )}
              />
            </View>
          </View>
        );

      case RecordType.MEAL:
        return (
          <View>
            <Text style={styles.label}>Refeição</Text>
            {renderRadioOptions(MEAL_TYPE_CHOICES, 'meal_type', 'meal_type_other')}
            <Text style={styles.label}>Aceitação</Text>
            {renderRadioOptions(MEAL_ACCEPTANCE_CHOICES, 'meal_acceptance', 'meal_acceptance_other')}
          </View>
        );

      case RecordType.SLEEP:
        return (
          <View>
            <Text style={styles.label}>Status do sono</Text>
            {renderRadioOptions(SLEEP_EVENT_CHOICES, 'sleep_event', 'sleep_event_other')}
          </View>
        );

      case RecordType.PROGRESS:
        return (
          <View>
            <Text style={styles.label}>Classificação</Text>
            <Controller
              control={control}
              name="progress_trend"
              render={({ field: { value, onChange } }) => (
                <View style={styles.pickerRow}>
                  {PROGRESS_TREND_OPTIONS.map((opt) => (
                    <TouchableOpacity
                      key={opt.value}
                      style={[
                        styles.pickerOption,
                        value === opt.value && styles.pickerOptionActive,
                      ]}
                      onPress={() => onChange(opt.value)}
                    >
                      <Text
                        style={[
                          styles.pickerOptionText,
                          value === opt.value && styles.pickerOptionTextActive,
                        ]}
                      >
                        {opt.label}
                      </Text>
                    </TouchableOpacity>
                  ))}
                </View>
              )}
            />
            {watch('progress_trend') === OTHER_VALUE && (
              <Controller
                control={control}
                name="progress_trend_other"
                render={({ field: { value, onChange } }) => (
                  <TextInput
                    style={[styles.input, { marginTop: spacing.sm }]}
                    value={value}
                    onChangeText={onChange}
                    placeholder="Descreva a classificação..."
                    placeholderTextColor={colors.textMuted}
                  />
                )}
              />
            )}
          </View>
        );

      case RecordType.ACTIVITY:
      case RecordType.OTHER:
      default:
        return (
          <View>
            <Text style={styles.label}>O quê</Text>
            <Controller
              control={control}
              name="what"
              render={({ field: { value, onChange } }) => (
                <TextInput
                  style={styles.input}
                  value={value}
                  onChangeText={onChange}
                  placeholder="Descreva a atividade"
                  placeholderTextColor={colors.textMuted}
                />
              )}
            />
          </View>
        );
    }
  };

  // ----- Step 1: Category Grid -----
  if (step === 1) {
    return (
      <SafeAreaView style={styles.safe} edges={['bottom']}>
        <ScrollView contentContainerStyle={styles.stepContainer}>
          <Text style={styles.stepTitle}>Selecione a categoria</Text>
          <View style={styles.categoryGrid}>
            {RECORD_TYPES.map((type) => {
              const meta = CATEGORY_META[type];
              if (!meta) return null;
              return (
                <TouchableOpacity
                  key={type}
                  style={[styles.categoryButton, { backgroundColor: meta.bg, borderColor: meta.color }]}
                  activeOpacity={0.7}
                  onPress={() => handleTypeSelect(type)}
                >
                  <Text style={styles.catEmoji}>{meta.icon}</Text>
                  <Text style={[styles.catLabel, { color: meta.color }]}>{meta.label}</Text>
                </TouchableOpacity>
              );
            })}
          </View>
        </ScrollView>
      </SafeAreaView>
    );
  }

  // ----- Step 2: Form -----
  return (
    <SafeAreaView style={styles.safe} edges={['bottom']}>
      <KeyboardAvoidingView
        style={{ flex: 1 }}
        behavior={Platform.OS === 'ios' ? 'padding' : undefined}
      >
        <ScrollView
          contentContainerStyle={styles.formContainer}
          keyboardShouldPersistTaps="handled"
        >
          {/* Category indicator */}
          <TouchableOpacity style={styles.categoryHeader} onPress={() => setStep(1)}>
            <Text style={styles.catHeaderEmoji}>
              {CATEGORY_META[selectedType]?.icon ?? '📝'}
            </Text>
            <Text style={styles.categoryHeaderLabel}>
              {CATEGORY_META[selectedType]?.label ?? selectedType}
            </Text>
            <Text style={styles.changeText}>Trocar ▸</Text>
          </TouchableOpacity>

          {/* Type-specific fields */}
          {renderTypeSpecificFields()}

          {/* Description (all types) */}
          <Text style={styles.label}>Observações</Text>
          <Controller
            control={control}
            name="description"
            render={({ field: { value, onChange } }) => (
              <TextInput
                style={[styles.input, styles.textArea]}
                value={value}
                onChangeText={onChange}
                placeholder="Detalhes adicionais..."
                placeholderTextColor={colors.textMuted}
                multiline
                numberOfLines={4}
                textAlignVertical="top"
              />
            )}
          />

          {/* Date picker */}
          <Controller
            control={control}
            name="date"
            render={({ field: { value, onChange } }) => (
              <DateTimePicker
                label="Data"
                value={value}
                mode="date"
                onChange={onChange}
              />
            )}
          />

          {/* Time picker */}
          <Controller
            control={control}
            name="time"
            render={({ field: { value, onChange } }) => (
              <DateTimePicker
                label="Horário"
                value={value}
                mode="time"
                onChange={onChange}
              />
            )}
          />

          {/* Is Exception */}
          <View style={styles.switchRow}>
            <Text style={styles.switchLabel}>Exceção</Text>
            <Controller
              control={control}
              name="is_exception"
              render={({ field: { value, onChange } }) => (
                <Switch
                  value={value}
                  onValueChange={onChange}
                  trackColor={{ false: colors.border, true: colors.primaryLight }}
                  thumbColor={value ? colors.primary : colors.textMuted}
                />
              )}
            />
          </View>

          {/* Recurrence */}
          <Text style={styles.label}>Repetição</Text>
          <Text style={styles.helpText}>Quando ativada, cria uma série até a data final.</Text>
          <Controller
            control={control}
            name="recurrence"
            render={({ field: { value, onChange } }) => (
              <View style={styles.pickerRow}>
                {RECURRENCE_OPTIONS.map((opt) => (
                  <TouchableOpacity
                    key={opt.value}
                    style={[
                      styles.pickerOption,
                      value === opt.value && styles.pickerOptionActive,
                    ]}
                    onPress={() => onChange(opt.value)}
                  >
                    <Text
                      style={[
                        styles.pickerOptionText,
                        value === opt.value && styles.pickerOptionTextActive,
                      ]}
                    >
                      {opt.label}
                    </Text>
                  </TouchableOpacity>
                ))}
              </View>
            )}
          />

          {/* Repeat until */}
          {selectedRecurrence !== Recurrence.NONE && (
            <>
              <Text style={styles.helpText}>Não pode ser anterior à Data.</Text>
              <Controller
                control={control}
                name="repeat_until"
                render={({ field: { value, onChange } }) => (
                  <DateTimePicker
                    label="Repetir até"
                    value={value || new Date()}
                    mode="date"
                    onChange={onChange}
                    minimumDate={watch('date')}
                  />
                )}
              />
            </>
          )}

          {/* Submit button */}
          <TouchableOpacity
            style={[styles.submitButton, submitting && styles.submitButtonDisabled]}
            onPress={handleSubmit(onSubmit)}
            disabled={submitting}
            activeOpacity={0.8}
          >
            {submitting ? (
              <ActivityIndicator color={colors.textInverse} />
            ) : (
              <Text style={styles.submitButtonText}>
                {editData ? 'Atualizar' : 'Salvar'}
              </Text>
            )}
          </TouchableOpacity>
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
  stepContainer: {
    padding: spacing.lg,
  },
  stepTitle: {
    fontSize: fontSize.xl,
    fontWeight: '600',
    color: colors.text,
    textAlign: 'center',
    marginBottom: spacing.lg,
  },
  categoryGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    justifyContent: 'space-between',
  },
  categoryButton: {
    width: '48%',
    borderRadius: borderRadius.lg,
    borderWidth: 2,
    padding: spacing.lg,
    alignItems: 'center',
    marginBottom: spacing.md,
  },
  catEmoji: {
    fontSize: 36,
    marginBottom: spacing.sm,
  },
  catLabel: {
    fontSize: fontSize.sm,
    fontWeight: '600',
    textAlign: 'center',
  },
  formContainer: {
    padding: spacing.lg,
    paddingBottom: spacing.xxl,
  },
  categoryHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.card,
    borderRadius: borderRadius.md,
    padding: spacing.md,
    marginBottom: spacing.lg,
  },
  catHeaderEmoji: {
    fontSize: 28,
    marginRight: spacing.sm,
  },
  categoryHeaderLabel: {
    flex: 1,
    fontSize: fontSize.md,
    fontWeight: '600',
    color: colors.text,
  },
  changeText: {
    fontSize: fontSize.sm,
    color: colors.primary,
    fontWeight: '500',
  },
  label: {
    fontSize: fontSize.sm,
    fontWeight: '600',
    color: colors.text,
    marginBottom: spacing.xs,
    marginTop: spacing.md,
  },
  helpText: {
    fontSize: fontSize.xs,
    color: colors.textSecondary,
    marginBottom: spacing.xs,
  },
  input: {
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: borderRadius.md,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.md,
    fontSize: fontSize.md,
    color: colors.text,
  },
  textArea: {
    minHeight: 100,
  },
  pickerRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: spacing.sm,
  },
  pickerOption: {
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    borderRadius: borderRadius.full,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.surface,
    marginBottom: spacing.xs,
  },
  pickerOptionActive: {
    backgroundColor: colors.primary,
    borderColor: colors.primary,
  },
  pickerOptionText: {
    fontSize: fontSize.sm,
    color: colors.text,
  },
  pickerOptionTextActive: {
    color: colors.textInverse,
    fontWeight: '600',
  },
  switchRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginTop: spacing.md,
    paddingVertical: spacing.sm,
  },
  switchLabel: {
    fontSize: fontSize.md,
    color: colors.text,
    flex: 1,
  },
  submitButton: {
    backgroundColor: colors.primary,
    borderRadius: borderRadius.md,
    paddingVertical: spacing.md,
    alignItems: 'center',
    justifyContent: 'center',
    marginTop: spacing.xl,
    minHeight: 50,
  },
  submitButtonDisabled: {
    backgroundColor: colors.primaryLight,
  },
  submitButtonText: {
    color: colors.textInverse,
    fontSize: fontSize.lg,
    fontWeight: '600',
  },
});
