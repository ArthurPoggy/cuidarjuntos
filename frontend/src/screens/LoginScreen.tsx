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
  Alert,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useNavigation } from '@react-navigation/native';
import { useAuth } from '../contexts/AuthContext';
import { colors, spacing, fontSize, borderRadius } from '../theme';
import type { AxiosError } from 'axios';
import { API_BASE_URL } from '../utils/constants';
import axios from 'axios';

export default function LoginScreen() {
  const navigation = useNavigation<any>();
  const { login } = useAuth();

  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleLogin = async () => {
    if (!username.trim() || !password.trim()) {
      setError('Preencha todos os campos.');
      return;
    }

    setError('');
    setLoading(true);

    try {
      await login(username.trim(), password);
    } catch (err) {
      const axiosErr = err as AxiosError<{ detail?: string; non_field_errors?: string[] }>;
      if (axiosErr.response?.data) {
        const data = axiosErr.response.data;
        if (data.detail) {
          setError(data.detail);
        } else if (data.non_field_errors) {
          setError(data.non_field_errors.join(' '));
        } else {
          setError('Credenciais invalidas. Tente novamente.');
        }
      } else {
        setError('Erro de conexao. Verifique sua internet.');
      }
    } finally {
      setLoading(false);
    }
  };

  const handleGuestLogin = async () => {
    setError('');
    setLoading(true);

    try {
      await login('visitante', 'demo123');
    } catch (err) {
      const axiosErr = err as AxiosError<{ detail?: string }>;
      if (axiosErr.response?.data?.detail) {
        setError(`Erro: ${axiosErr.response.data.detail}`);
      } else if (axiosErr.message) {
        setError(`Erro de conexão: ${axiosErr.message}. Verifique se o backend está rodando em http://192.168.0.4:8000`);
      } else {
        setError('Erro ao entrar como visitante. Verifique sua conexão.');
      }
      console.error('Erro no login visitante:', err);
    } finally {
      setLoading(false);
    }
  };

  const testConnection = async () => {
    try {
      // Testar endpoint GET simples (schema ou docs)
      const response = await axios.get(`${API_BASE_URL.replace('/api/v1', '')}/api/v1/schema/`, {
        timeout: 5000,
      });
      Alert.alert(
        '✅ Conexão OK!',
        `Backend acessível!\n\nURL: ${API_BASE_URL}\nStatus: ${response.status}\n\nAgora tente fazer login.`,
        [{ text: 'OK' }]
      );
    } catch (err: any) {
      Alert.alert(
        '❌ Erro de Conexão',
        `Não foi possível conectar ao backend.\n\nURL: ${API_BASE_URL}\n\nErro: ${err.message}\n\nVerifique:\n1. Backend rodando com: python manage.py runserver 0.0.0.0:8000\n2. Celular e PC na mesma rede Wi-Fi\n3. Firewall permite porta 8000\n4. IP configurado: ${API_BASE_URL.split('/')[2].split(':')[0]}`,
        [{ text: 'OK' }]
      );
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
          <View style={styles.header}>
            <Text style={styles.appName}>CuidarJuntos</Text>
            <Text style={styles.subtitle}>Cuidado colaborativo para quem voce ama</Text>

            {/* Botão Configurar IP */}
            <TouchableOpacity
              style={styles.settingsButton}
              onPress={() => navigation.navigate('Settings')}
            >
              <Text style={styles.settingsButtonText}>
                ⚙️ Configurar IP do Backend
              </Text>
            </TouchableOpacity>

            {/* Debug: Testar Conexão */}
            <TouchableOpacity
              style={styles.debugButton}
              onPress={testConnection}
            >
              <Text style={styles.debugButtonText}>
                🔍 Testar Conexão com Backend
              </Text>
            </TouchableOpacity>
          </View>

          <View style={styles.card}>
            <Text style={styles.cardTitle}>Entrar</Text>

            {error !== '' && (
              <View style={styles.errorBox}>
                <Text style={styles.errorText}>{error}</Text>
              </View>
            )}

            <Text style={styles.label}>Usuario</Text>
            <TextInput
              style={styles.input}
              placeholder="Seu nome de usuario"
              placeholderTextColor={colors.textMuted}
              autoCapitalize="none"
              autoCorrect={false}
              value={username}
              onChangeText={setUsername}
              editable={!loading}
            />

            <Text style={styles.label}>Senha</Text>
            <TextInput
              style={styles.input}
              placeholder="Sua senha"
              placeholderTextColor={colors.textMuted}
              secureTextEntry
              value={password}
              onChangeText={setPassword}
              editable={!loading}
              onSubmitEditing={handleLogin}
            />

            <TouchableOpacity
              style={[styles.button, loading && styles.buttonDisabled]}
              onPress={handleLogin}
              disabled={loading}
              activeOpacity={0.8}
            >
              {loading ? (
                <ActivityIndicator color={colors.textInverse} />
              ) : (
                <Text style={styles.buttonText}>Entrar</Text>
              )}
            </TouchableOpacity>

            <TouchableOpacity
              style={styles.linkButton}
              onPress={() => navigation.navigate('PasswordReset')}
            >
              <Text style={styles.linkText}>Esqueceu a senha?</Text>
            </TouchableOpacity>

            {/* Separador */}
            <View style={styles.divider}>
              <View style={styles.dividerLine} />
              <Text style={styles.dividerText}>ou</Text>
              <View style={styles.dividerLine} />
            </View>

            {/* Botão Visitante */}
            <TouchableOpacity
              style={[styles.guestButton, loading && styles.buttonDisabled]}
              onPress={handleGuestLogin}
              disabled={loading}
              activeOpacity={0.8}
            >
              <Text style={styles.guestButtonText}>
                👤 Entrar como Visitante
              </Text>
              <Text style={styles.guestButtonSubtext}>
                Testar o app sem criar conta
              </Text>
            </TouchableOpacity>
          </View>

          <View style={styles.footer}>
            <Text style={styles.footerText}>Nao tem uma conta?</Text>
            <TouchableOpacity onPress={() => navigation.navigate('Register')}>
              <Text style={styles.footerLink}> Cadastre-se</Text>
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
    justifyContent: 'center',
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.xl,
  },
  header: {
    alignItems: 'center',
    marginBottom: spacing.xl,
  },
  appName: {
    fontSize: fontSize.title,
    fontWeight: '700',
    color: colors.primary,
    marginBottom: spacing.xs,
  },
  subtitle: {
    fontSize: fontSize.sm,
    color: colors.textSecondary,
    textAlign: 'center',
    marginBottom: spacing.sm,
  },
  settingsButton: {
    marginTop: spacing.sm,
    paddingVertical: spacing.sm,
    paddingHorizontal: spacing.md,
    backgroundColor: colors.primary,
    borderRadius: borderRadius.md,
  },
  settingsButtonText: {
    fontSize: fontSize.sm,
    color: colors.textInverse,
    textAlign: 'center',
    fontWeight: '600',
  },
  debugButton: {
    marginTop: spacing.xs,
    paddingVertical: spacing.xs,
    paddingHorizontal: spacing.md,
    backgroundColor: colors.borderLight,
    borderRadius: borderRadius.full,
  },
  debugButtonText: {
    fontSize: fontSize.xs,
    color: colors.textSecondary,
    textAlign: 'center',
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
  label: {
    fontSize: fontSize.sm,
    fontWeight: '500',
    color: colors.text,
    marginBottom: spacing.xs,
    marginTop: spacing.sm,
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
  linkButton: {
    alignItems: 'center',
    marginTop: spacing.md,
  },
  linkText: {
    color: colors.primary,
    fontSize: fontSize.sm,
  },
  divider: {
    flexDirection: 'row',
    alignItems: 'center',
    marginVertical: spacing.lg,
  },
  dividerLine: {
    flex: 1,
    height: 1,
    backgroundColor: colors.border,
  },
  dividerText: {
    marginHorizontal: spacing.md,
    color: colors.textMuted,
    fontSize: fontSize.sm,
  },
  guestButton: {
    backgroundColor: colors.surface,
    borderWidth: 2,
    borderColor: colors.primary,
    borderRadius: borderRadius.md,
    paddingVertical: spacing.md,
    paddingHorizontal: spacing.lg,
    alignItems: 'center',
    justifyContent: 'center',
    minHeight: 60,
  },
  guestButtonText: {
    color: colors.primary,
    fontSize: fontSize.md,
    fontWeight: '600',
    marginBottom: 4,
  },
  guestButtonSubtext: {
    color: colors.textSecondary,
    fontSize: fontSize.xs,
  },
  footer: {
    flexDirection: 'row',
    justifyContent: 'center',
    marginTop: spacing.lg,
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
