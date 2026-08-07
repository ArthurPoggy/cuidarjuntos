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
import { useNavigation } from '@react-navigation/native';
import { useAuth } from '../contexts/AuthContext';
import { colors, spacing, fontSize, borderRadius } from '../theme';
import type { AxiosError } from 'axios';
import {
  formatCpf,
  formatDateInput,
  parseDateToISO,
  validateRegisterField,
  validateRegisterForm,
  type RegisterFormValues,
  type RegisterFormErrors,
} from '../utils/validation';

type RegisterField = keyof RegisterFormValues;

interface ApiFieldErrors {
  [key: string]: string[];
}

const FIELD_ORDER: RegisterField[] = [
  'full_name',
  'cpf',
  'birth_date',
  'email',
  'username',
  'password',
];

export default function RegisterScreen() {
  const navigation = useNavigation<any>();
  const { register } = useAuth();

  const [values, setValues] = useState<RegisterFormValues>({
    full_name: '',
    cpf: '',
    birth_date: '',
    email: '',
    username: '',
    password: '',
  });
  const [touched, setTouched] = useState<Partial<Record<RegisterField, boolean>>>({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [fieldErrors, setFieldErrors] = useState<RegisterFormErrors>({});

  const setValue = (field: RegisterField, rawValue: string) => {
    let value = rawValue;
    if (field === 'cpf') value = formatCpf(rawValue);
    if (field === 'birth_date') value = formatDateInput(rawValue);

    const nextValues = { ...values, [field]: value };
    setValues(nextValues);

    // Feedback em tempo real: revalida o campo assim que ele ja foi visitado
    // (perdeu foco pelo menos uma vez) ou ja exibia um erro.
    if (touched[field] || fieldErrors[field]) {
      const fieldError = validateRegisterField(field, nextValues);
      setFieldErrors((prev) => {
        const next = { ...prev };
        if (fieldError) {
          next[field] = fieldError;
        } else {
          delete next[field];
        }
        return next;
      });
    }
  };

  const handleBlur = (field: RegisterField) => {
    setTouched((prev) => ({ ...prev, [field]: true }));
    const fieldError = validateRegisterField(field, values);
    setFieldErrors((prev) => {
      const next = { ...prev };
      if (fieldError) {
        next[field] = fieldError;
      } else {
        delete next[field];
      }
      return next;
    });
  };

  const handleRegister = async () => {
    setError('');

    const validationErrors = validateRegisterForm(values);
    if (Object.keys(validationErrors).length > 0) {
      setFieldErrors(validationErrors);
      setTouched(
        FIELD_ORDER.reduce((acc, field) => ({ ...acc, [field]: true }), {} as Record<RegisterField, boolean>)
      );
      return;
    }

    setFieldErrors({});

    const rawCpf = values.cpf.replace(/\D/g, '');
    const isoDate = parseDateToISO(values.birth_date);

    setLoading(true);

    try {
      await register({
        full_name: values.full_name.trim(),
        cpf: rawCpf,
        birth_date: isoDate,
        email: values.email.trim(),
        username: values.username.trim(),
        password: values.password,
      });
    } catch (err) {
      const axiosErr = err as AxiosError<ApiFieldErrors & { detail?: string; non_field_errors?: string[] }>;
      if (axiosErr.response?.data) {
        const data = axiosErr.response.data;
        if (data.detail) {
          setError(data.detail);
        } else if (data.non_field_errors) {
          setError(data.non_field_errors.join(' '));
        } else {
          const errors: RegisterFormErrors = {};
          Object.entries(data).forEach(([key, val]) => {
            if (Array.isArray(val) && FIELD_ORDER.includes(key as RegisterField)) {
              errors[key as RegisterField] = (val as string[]).join(' ');
            }
          });
          if (Object.keys(errors).length > 0) {
            setFieldErrors(errors);
          } else {
            setError('Erro ao criar conta. Tente novamente.');
          }
        }
      } else {
        setError('Erro de conexao. Verifique sua internet.');
      }
    } finally {
      setLoading(false);
    }
  };

  const getFieldError = (field: RegisterField): string | null => fieldErrors[field] ?? null;

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
          <View style={styles.header}>
            <Text style={styles.appName}>CuidarJuntos</Text>
            <Text style={styles.subtitle}>Crie sua conta</Text>
          </View>

          <View style={styles.card}>
            {error !== '' && (
              <View style={styles.errorBox}>
                <Text style={styles.errorText}>{error}</Text>
              </View>
            )}

            <Text style={styles.label}>Nome Completo *</Text>
            <TextInput
              style={[styles.input, getFieldError('full_name') && styles.inputError]}
              placeholder="Seu nome completo"
              placeholderTextColor={colors.textMuted}
              value={values.full_name}
              onChangeText={(text) => setValue('full_name', text)}
              onBlur={() => handleBlur('full_name')}
              editable={!loading}
              accessibilityLabel="Campo de nome completo"
            />
            {getFieldError('full_name') && (
              <Text style={styles.fieldError}>{getFieldError('full_name')}</Text>
            )}

            <Text style={styles.label}>CPF *</Text>
            <TextInput
              style={[styles.input, getFieldError('cpf') && styles.inputError]}
              placeholder="000.000.000-00"
              placeholderTextColor={colors.textMuted}
              keyboardType="numeric"
              value={values.cpf}
              onChangeText={(text) => setValue('cpf', text)}
              onBlur={() => handleBlur('cpf')}
              editable={!loading}
              maxLength={14}
              accessibilityLabel="Campo de CPF"
            />
            {getFieldError('cpf') && (
              <Text style={styles.fieldError}>{getFieldError('cpf')}</Text>
            )}

            <Text style={styles.label}>Data de Nascimento</Text>
            <TextInput
              style={[styles.input, getFieldError('birth_date') && styles.inputError]}
              placeholder="DD/MM/AAAA"
              placeholderTextColor={colors.textMuted}
              keyboardType="numeric"
              value={values.birth_date}
              onChangeText={(text) => setValue('birth_date', text)}
              onBlur={() => handleBlur('birth_date')}
              editable={!loading}
              maxLength={10}
              accessibilityLabel="Campo de data de nascimento"
            />
            {getFieldError('birth_date') && (
              <Text style={styles.fieldError}>{getFieldError('birth_date')}</Text>
            )}

            <Text style={styles.label}>E-mail *</Text>
            <TextInput
              style={[styles.input, getFieldError('email') && styles.inputError]}
              placeholder="seuemail@exemplo.com"
              placeholderTextColor={colors.textMuted}
              keyboardType="email-address"
              autoCapitalize="none"
              autoCorrect={false}
              value={values.email}
              onChangeText={(text) => setValue('email', text)}
              onBlur={() => handleBlur('email')}
              editable={!loading}
              accessibilityLabel="Campo de e-mail"
            />
            {getFieldError('email') && (
              <Text style={styles.fieldError}>{getFieldError('email')}</Text>
            )}

            <Text style={styles.label}>Usuario *</Text>
            <TextInput
              style={[styles.input, getFieldError('username') && styles.inputError]}
              placeholder="Escolha um nome de usuario"
              placeholderTextColor={colors.textMuted}
              autoCapitalize="none"
              autoCorrect={false}
              value={values.username}
              onChangeText={(text) => setValue('username', text)}
              onBlur={() => handleBlur('username')}
              editable={!loading}
              accessibilityLabel="Campo de usuario"
            />
            {getFieldError('username') && (
              <Text style={styles.fieldError}>{getFieldError('username')}</Text>
            )}

            <Text style={styles.label}>Senha *</Text>
            <TextInput
              style={[styles.input, getFieldError('password') && styles.inputError]}
              placeholder="Crie uma senha segura"
              placeholderTextColor={colors.textMuted}
              secureTextEntry
              value={values.password}
              onChangeText={(text) => setValue('password', text)}
              onBlur={() => handleBlur('password')}
              editable={!loading}
              accessibilityLabel="Campo de senha"
            />
            {getFieldError('password') && (
              <Text style={styles.fieldError}>{getFieldError('password')}</Text>
            )}

            <TouchableOpacity
              style={[styles.button, loading && styles.buttonDisabled]}
              onPress={handleRegister}
              disabled={loading}
              activeOpacity={0.8}
              accessibilityRole="button"
              accessibilityLabel="Criar Conta"
              accessibilityState={{ disabled: loading, busy: loading }}
            >
              {loading ? (
                <ActivityIndicator color={colors.textInverse} />
              ) : (
                <Text style={styles.buttonText}>Criar Conta</Text>
              )}
            </TouchableOpacity>
          </View>

          <View style={styles.footer}>
            <Text style={styles.footerText}>Ja tem uma conta?</Text>
            <TouchableOpacity
              onPress={() => navigation.navigate('Login')}
              accessibilityRole="button"
              accessibilityLabel="Entrar"
              hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
            >
              <Text style={styles.footerLink}> Entrar</Text>
            </TouchableOpacity>
          </View>

          <View style={styles.footer}>
            <TouchableOpacity
              onPress={() => navigation.navigate('PasswordReset')}
              accessibilityRole="button"
              accessibilityLabel="Esqueceu a senha?"
              hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
            >
              <Text style={styles.footerLink}>Esqueceu a senha?</Text>
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
    paddingVertical: spacing.xl,
  },
  header: {
    alignItems: 'center',
    marginBottom: spacing.lg,
  },
  appName: {
    fontSize: fontSize.xxl,
    fontWeight: '700',
    color: colors.primary,
    marginBottom: spacing.xs,
  },
  subtitle: {
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
  fieldError: {
    color: colors.danger,
    fontSize: fontSize.xs,
    marginTop: spacing.xs,
  },
  button: {
    backgroundColor: colors.primary,
    borderRadius: borderRadius.md,
    paddingVertical: spacing.md,
    alignItems: 'center',
    justifyContent: 'center',
    marginTop: spacing.lg,
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
  footer: {
    flexDirection: 'row',
    justifyContent: 'center',
    marginTop: spacing.lg,
    marginBottom: spacing.lg,
  },
  footerText: {
    color: colors.textSecondary,
    fontSize: fontSize.sm,
  },
  footerLink: {
    color: colors.primary,
    fontSize: fontSize.sm,
    fontWeight: '600',
  },
});
