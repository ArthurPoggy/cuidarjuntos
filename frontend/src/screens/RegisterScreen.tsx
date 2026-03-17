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

interface FieldErrors {
  [key: string]: string[];
}

export default function RegisterScreen() {
  const navigation = useNavigation<any>();
  const { register } = useAuth();

  const [fullName, setFullName] = useState('');
  const [cpf, setCpf] = useState('');
  const [birthDate, setBirthDate] = useState('');
  const [email, setEmail] = useState('');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});

  const formatCpf = (value: string): string => {
    const digits = value.replace(/\D/g, '').slice(0, 11);
    if (digits.length <= 3) return digits;
    if (digits.length <= 6) return `${digits.slice(0, 3)}.${digits.slice(3)}`;
    if (digits.length <= 9)
      return `${digits.slice(0, 3)}.${digits.slice(3, 6)}.${digits.slice(6)}`;
    return `${digits.slice(0, 3)}.${digits.slice(3, 6)}.${digits.slice(6, 9)}-${digits.slice(9)}`;
  };

  const handleCpfChange = (value: string) => {
    setCpf(formatCpf(value));
  };

  const formatDateInput = (value: string): string => {
    const digits = value.replace(/\D/g, '').slice(0, 8);
    if (digits.length <= 2) return digits;
    if (digits.length <= 4) return `${digits.slice(0, 2)}/${digits.slice(2)}`;
    return `${digits.slice(0, 2)}/${digits.slice(2, 4)}/${digits.slice(4)}`;
  };

  const handleBirthDateChange = (value: string) => {
    setBirthDate(formatDateInput(value));
  };

  const parseDateToISO = (dateStr: string): string | undefined => {
    if (!dateStr.trim()) return undefined;
    const parts = dateStr.split('/');
    if (parts.length !== 3) return undefined;
    const [day, month, year] = parts;
    if (day.length !== 2 || month.length !== 2 || year.length !== 4) return undefined;
    return `${year}-${month}-${day}`;
  };

  const handleRegister = async () => {
    setError('');
    setFieldErrors({});

    if (!fullName.trim() || !cpf.trim() || !email.trim() || !username.trim() || !password.trim()) {
      setError('Preencha todos os campos obrigatorios.');
      return;
    }

    const rawCpf = cpf.replace(/\D/g, '');
    if (rawCpf.length !== 11) {
      setFieldErrors({ cpf: ['CPF deve conter 11 digitos.'] });
      return;
    }

    const isoDate = parseDateToISO(birthDate);

    setLoading(true);

    try {
      await register({
        full_name: fullName.trim(),
        cpf: rawCpf,
        birth_date: isoDate,
        email: email.trim(),
        username: username.trim(),
        password,
      });
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

  const getFieldError = (field: string): string | null => {
    if (fieldErrors[field] && fieldErrors[field].length > 0) {
      return fieldErrors[field].join(' ');
    }
    return null;
  };

  const fieldLabels: Record<string, string> = {
    full_name: 'Nome Completo',
    cpf: 'CPF',
    birth_date: 'Data de Nascimento',
    email: 'E-mail',
    username: 'Usuario',
    password: 'Senha',
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
              value={fullName}
              onChangeText={setFullName}
              editable={!loading}
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
              value={cpf}
              onChangeText={handleCpfChange}
              editable={!loading}
              maxLength={14}
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
              value={birthDate}
              onChangeText={handleBirthDateChange}
              editable={!loading}
              maxLength={10}
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
              value={email}
              onChangeText={setEmail}
              editable={!loading}
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
              value={username}
              onChangeText={setUsername}
              editable={!loading}
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
              value={password}
              onChangeText={setPassword}
              editable={!loading}
            />
            {getFieldError('password') && (
              <Text style={styles.fieldError}>{getFieldError('password')}</Text>
            )}

            <TouchableOpacity
              style={[styles.button, loading && styles.buttonDisabled]}
              onPress={handleRegister}
              disabled={loading}
              activeOpacity={0.8}
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
            <TouchableOpacity onPress={() => navigation.navigate('Login')}>
              <Text style={styles.footerLink}> Entrar</Text>
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
