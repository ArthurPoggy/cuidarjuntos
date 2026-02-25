import React, { useState } from 'react';
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  StyleSheet,
  Alert,
  ScrollView,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { colors, spacing, fontSize, borderRadius } from '../theme';

export default function SettingsScreen() {
  const [customIP, setCustomIP] = useState('');

  const saveCustomIP = async () => {
    if (!customIP.trim()) {
      Alert.alert('Erro', 'Digite um IP válido');
      return;
    }

    try {
      await AsyncStorage.setItem('custom_api_ip', customIP.trim());
      Alert.alert(
        'Sucesso!',
        `IP configurado: ${customIP}\n\nReinicie o app para aplicar.`,
        [{ text: 'OK' }]
      );
    } catch (error) {
      Alert.alert('Erro', 'Não foi possível salvar');
    }
  };

  const clearCustomIP = async () => {
    try {
      await AsyncStorage.removeItem('custom_api_ip');
      setCustomIP('');
      Alert.alert(
        'IP Resetado',
        'Usando IP padrão do código.\n\nReinicie o app.',
        [{ text: 'OK' }]
      );
    } catch (error) {
      Alert.alert('Erro', 'Não foi possível resetar');
    }
  };

  const loadCurrentIP = async () => {
    const saved = await AsyncStorage.getItem('custom_api_ip');
    if (saved) {
      Alert.alert('IP Atual', `IP configurado: ${saved}`);
    } else {
      Alert.alert('IP Atual', 'Usando IP padrão: 10.0.2.2');
    }
  };

  return (
    <SafeAreaView style={styles.safe}>
      <ScrollView contentContainerStyle={styles.container}>
        <Text style={styles.title}>⚙️ Configurações de Conexão</Text>

        <View style={styles.section}>
          <Text style={styles.label}>IP do Backend</Text>
          <Text style={styles.hint}>
            Digite o IP do seu computador (sem http://, sem :8000)
          </Text>
          <Text style={styles.hint}>
            Exemplo: 192.168.0.10 ou 192.168.x.x
          </Text>

          <TextInput
            style={styles.input}
            placeholder="192.168.x.x"
            placeholderTextColor={colors.textMuted}
            value={customIP}
            onChangeText={setCustomIP}
            autoCapitalize="none"
            keyboardType="numbers-and-punctuation"
          />

          <TouchableOpacity style={styles.button} onPress={saveCustomIP}>
            <Text style={styles.buttonText}>💾 Salvar IP Customizado</Text>
          </TouchableOpacity>

          <TouchableOpacity style={styles.buttonSecondary} onPress={clearCustomIP}>
            <Text style={styles.buttonSecondaryText}>🔄 Resetar para Padrão</Text>
          </TouchableOpacity>

          <TouchableOpacity style={styles.buttonSecondary} onPress={loadCurrentIP}>
            <Text style={styles.buttonSecondaryText}>ℹ️ Ver IP Atual</Text>
          </TouchableOpacity>
        </View>

        <View style={styles.infoBox}>
          <Text style={styles.infoTitle}>Como encontrar seu IP:</Text>
          <Text style={styles.infoText}>1. Abra o Prompt de Comando (cmd)</Text>
          <Text style={styles.infoText}>2. Digite: ipconfig</Text>
          <Text style={styles.infoText}>3. Procure "IPv4" da sua rede Wi-Fi</Text>
          <Text style={styles.infoText}>4. Copie apenas os números (ex: 192.168.0.10)</Text>
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: {
    flex: 1,
    backgroundColor: colors.background,
  },
  container: {
    padding: spacing.lg,
  },
  title: {
    fontSize: fontSize.xl,
    fontWeight: '700',
    color: colors.text,
    marginBottom: spacing.lg,
    textAlign: 'center',
  },
  section: {
    backgroundColor: colors.surface,
    borderRadius: borderRadius.lg,
    padding: spacing.lg,
    marginBottom: spacing.lg,
  },
  label: {
    fontSize: fontSize.md,
    fontWeight: '600',
    color: colors.text,
    marginBottom: spacing.xs,
  },
  hint: {
    fontSize: fontSize.xs,
    color: colors.textSecondary,
    marginBottom: spacing.xs,
  },
  input: {
    backgroundColor: colors.background,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: borderRadius.md,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.md,
    fontSize: fontSize.lg,
    color: colors.text,
    marginTop: spacing.sm,
    marginBottom: spacing.md,
    textAlign: 'center',
    fontWeight: '600',
  },
  button: {
    backgroundColor: colors.primary,
    borderRadius: borderRadius.md,
    paddingVertical: spacing.md,
    alignItems: 'center',
    marginBottom: spacing.sm,
  },
  buttonText: {
    color: colors.textInverse,
    fontSize: fontSize.md,
    fontWeight: '600',
  },
  buttonSecondary: {
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: borderRadius.md,
    paddingVertical: spacing.md,
    alignItems: 'center',
    marginBottom: spacing.sm,
  },
  buttonSecondaryText: {
    color: colors.text,
    fontSize: fontSize.sm,
    fontWeight: '600',
  },
  infoBox: {
    backgroundColor: '#EFF6FF',
    borderWidth: 1,
    borderColor: '#BFDBFE',
    borderRadius: borderRadius.md,
    padding: spacing.md,
  },
  infoTitle: {
    fontSize: fontSize.sm,
    fontWeight: '600',
    color: colors.primary,
    marginBottom: spacing.xs,
  },
  infoText: {
    fontSize: fontSize.xs,
    color: colors.text,
    marginBottom: 2,
  },
});
