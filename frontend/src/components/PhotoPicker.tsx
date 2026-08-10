import React from 'react';
import { View, Text, TouchableOpacity, Image, StyleSheet, Alert } from 'react-native';
import * as ImagePicker from 'expo-image-picker';
import { colors, spacing, fontSize, borderRadius } from '../theme';

export interface PickedPhoto {
  uri: string;
  name: string;
  type: string;
}

interface PhotoPickerProps {
  label?: string;
  // uri de uma foto já anexada ao registro (ex.: vinda do backend), usada
  // como preview quando nenhuma foto nova foi selecionada ainda.
  existingUri?: string | null;
  // undefined: usuário ainda não mexeu na foto (preview cai para existingUri).
  // null: usuário removeu explicitamente a foto (existente ou recém-escolhida).
  // PickedPhoto: usuário selecionou uma foto nova.
  value: PickedPhoto | null | undefined;
  onChange: (photo: PickedPhoto | null | undefined) => void;
  // Headers para carregar `existingUri`: a foto do backend agora fica atras
  // de uma view autenticada (ver RecordDetailScreen), entao o preview de uma
  // foto já anexada precisa do Bearer token. Sem efeito sobre fotos locais
  // recém-escolhidas (file://), que não passam por essa rota.
  authHeaders?: Record<string, string>;
}

function guessNameAndType(uri: string): { name: string; type: string } {
  const match = /\.(\w+)$/.exec(uri.split('?')[0]);
  const ext = (match?.[1] || 'jpg').toLowerCase();
  const type = ext === 'png' ? 'image/png' : ext === 'heic' ? 'image/heic' : 'image/jpeg';
  return { name: `foto.${ext}`, type };
}

export default function PhotoPicker({
  label = 'Foto', existingUri, value, onChange, authHeaders,
}: PhotoPickerProps) {
  const pickFrom = async (source: 'camera' | 'library') => {
    const permission =
      source === 'camera'
        ? await ImagePicker.requestCameraPermissionsAsync()
        : await ImagePicker.requestMediaLibraryPermissionsAsync();

    if (!permission.granted) {
      Alert.alert('Permissão necessária', 'Autorize o acesso para anexar uma foto.');
      return;
    }

    const result =
      source === 'camera'
        ? await ImagePicker.launchCameraAsync({ quality: 0.7, allowsEditing: true })
        : await ImagePicker.launchImageLibraryAsync({ quality: 0.7, allowsEditing: true });

    if (result.canceled || !result.assets?.length) return;

    const asset = result.assets[0];
    const { name, type } = guessNameAndType(asset.uri);
    onChange({ uri: asset.uri, name, type });
  };

  const handlePress = () => {
    Alert.alert('Anexar foto', 'Escolha a origem da foto', [
      { text: 'Câmera', onPress: () => pickFrom('camera') },
      { text: 'Galeria', onPress: () => pickFrom('library') },
      { text: 'Cancelar', style: 'cancel' },
    ]);
  };

  // value === null significa remoção explícita: nunca cai de volta para a
  // foto existente, senão o botão "Remover" nunca conseguiria limpar o preview.
  const previewUri = value === null ? null : value?.uri ?? existingUri ?? null;
  // Headers só fazem sentido para a foto vinda do backend (existingUri), não
  // para um arquivo local recém-escolhido pelo picker (value.uri).
  const isRemotePreview = !value && previewUri === existingUri;

  return (
    <View>
      <Text style={styles.label}>{label}</Text>
      {previewUri ? (
        <View style={styles.previewWrap}>
          <Image
            source={
              isRemotePreview && authHeaders
                ? { uri: previewUri, headers: authHeaders }
                : { uri: previewUri }
            }
            style={styles.preview}
          />
          <View style={styles.previewActions}>
            <TouchableOpacity style={styles.actionButton} onPress={handlePress}>
              <Text style={styles.actionButtonText}>Trocar</Text>
            </TouchableOpacity>
            <TouchableOpacity
              style={[styles.actionButton, styles.removeButton]}
              onPress={() => onChange(null)}
            >
              <Text style={[styles.actionButtonText, styles.removeButtonText]}>Remover</Text>
            </TouchableOpacity>
          </View>
        </View>
      ) : (
        <TouchableOpacity style={styles.addButton} onPress={handlePress} activeOpacity={0.7}>
          <Text style={styles.addButtonText}>+ Adicionar foto</Text>
        </TouchableOpacity>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  label: {
    fontSize: fontSize.sm,
    fontWeight: '600',
    color: colors.text,
    marginBottom: spacing.xs,
    marginTop: spacing.md,
  },
  addButton: {
    borderWidth: 1,
    borderStyle: 'dashed',
    borderColor: colors.border,
    borderRadius: borderRadius.md,
    paddingVertical: spacing.lg,
    alignItems: 'center',
    backgroundColor: colors.surface,
  },
  addButtonText: {
    color: colors.primary,
    fontSize: fontSize.md,
    fontWeight: '600',
  },
  previewWrap: {
    alignItems: 'center',
  },
  preview: {
    width: '100%',
    height: 200,
    borderRadius: borderRadius.md,
    backgroundColor: colors.borderLight,
  },
  previewActions: {
    flexDirection: 'row',
    gap: spacing.sm,
    marginTop: spacing.sm,
  },
  actionButton: {
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    borderRadius: borderRadius.md,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.surface,
  },
  actionButtonText: {
    color: colors.text,
    fontSize: fontSize.sm,
    fontWeight: '600',
  },
  removeButton: {
    borderColor: colors.danger,
  },
  removeButtonText: {
    color: colors.danger,
  },
});
