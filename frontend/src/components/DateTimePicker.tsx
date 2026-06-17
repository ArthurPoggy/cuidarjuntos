import React, { useState } from 'react';
import { View, Text, TouchableOpacity, StyleSheet, Platform, Modal } from 'react-native';
import RNDateTimePicker from '@react-native-community/datetimepicker';
import { colors, spacing, borderRadius, fontSize } from '../theme';

interface Props {
  label: string;
  value: Date;
  mode: 'date' | 'time';
  onChange: (date: Date) => void;
  minimumDate?: Date;
  maximumDate?: Date;
  error?: string;
}

export default function DateTimePicker({
  label,
  value,
  mode,
  onChange,
  minimumDate,
  maximumDate,
  error,
}: Props) {
  const [show, setShow] = useState(false);

  const formatValue = (date: Date) => {
    if (mode === 'date') {
      return date.toLocaleDateString('pt-BR');
    } else {
      return date.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' });
    }
  };

  const handleChange = (event: any, selectedDate?: Date) => {
    if (Platform.OS === 'android') {
      setShow(false);
    }
    if (selectedDate) {
      onChange(selectedDate);
    }
  };

  // --- Web: usa o input nativo do navegador (RNDateTimePicker não roda na web) ---
  const toInputValue = (date: Date) => {
    const pad = (n: number) => String(n).padStart(2, '0');
    if (mode === 'date') {
      return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
    }
    return `${pad(date.getHours())}:${pad(date.getMinutes())}`;
  };

  const handleWebChange = (e: { target: { value: string } }) => {
    const v = e.target.value;
    if (!v) return;
    const next = new Date(value);
    if (mode === 'date') {
      const [y, m, d] = v.split('-').map(Number);
      next.setFullYear(y, m - 1, d);
    } else {
      const [hh, mm] = v.split(':').map(Number);
      next.setHours(hh, mm, 0, 0);
    }
    onChange(next);
  };

  if (Platform.OS === 'web') {
    return (
      <View style={styles.container}>
        <Text style={styles.label}>{label}</Text>
        {React.createElement('input', {
          type: mode,
          value: toInputValue(value),
          onChange: handleWebChange,
          min: minimumDate ? toInputValue(minimumDate) : undefined,
          max: maximumDate ? toInputValue(maximumDate) : undefined,
          style: {
            backgroundColor: colors.surface,
            border: `1px solid ${error ? colors.danger : colors.border}`,
            borderRadius: 8,
            padding: 12,
            fontSize: 16,
            color: colors.text,
            width: '100%',
            boxSizing: 'border-box',
          },
        })}
        {error ? <Text style={styles.errorText}>{error}</Text> : null}
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <Text style={styles.label}>{label}</Text>
      <TouchableOpacity
        style={[styles.input, error && styles.inputError]}
        onPress={() => setShow(true)}
      >
        <Text style={styles.valueText}>{formatValue(value)}</Text>
        <Text style={styles.icon}>{mode === 'date' ? '📅' : '🕐'}</Text>
      </TouchableOpacity>
      {error && <Text style={styles.errorText}>{error}</Text>}

      {/* Android: show picker directly */}
      {show && Platform.OS === 'android' && (
        <RNDateTimePicker
          value={value}
          mode={mode}
          is24Hour={true}
          display="default"
          onChange={handleChange}
          minimumDate={minimumDate}
          maximumDate={maximumDate}
        />
      )}

      {/* iOS: show picker in modal */}
      {show && Platform.OS === 'ios' && (
        <Modal
          transparent={true}
          animationType="slide"
          visible={show}
          onRequestClose={() => setShow(false)}
        >
          <TouchableOpacity
            style={styles.iosModalOverlay}
            activeOpacity={1}
            onPress={() => setShow(false)}
          >
            <TouchableOpacity
              style={styles.iosModal}
              activeOpacity={1}
              onPress={(e) => e.stopPropagation()}
            >
              <View style={styles.iosHeader}>
                <TouchableOpacity onPress={() => setShow(false)}>
                  <Text style={styles.iosDoneButton}>Confirmar</Text>
                </TouchableOpacity>
              </View>
              <RNDateTimePicker
                value={value}
                mode={mode}
                is24Hour={true}
                display="spinner"
                onChange={(event, date) => {
                  if (date) onChange(date);
                }}
                minimumDate={minimumDate}
                maximumDate={maximumDate}
              />
            </TouchableOpacity>
          </TouchableOpacity>
        </Modal>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    marginBottom: spacing.md,
  },
  label: {
    fontSize: fontSize.sm,
    fontWeight: '600',
    color: colors.text,
    marginBottom: spacing.xs,
  },
  input: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: borderRadius.md,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm + 2,
  },
  inputError: {
    borderColor: colors.danger,
  },
  valueText: {
    fontSize: fontSize.md,
    color: colors.text,
  },
  icon: {
    fontSize: 20,
  },
  errorText: {
    fontSize: fontSize.xs,
    color: colors.danger,
    marginTop: 4,
  },
  iosModalOverlay: {
    position: 'absolute',
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    backgroundColor: 'rgba(0,0,0,0.5)',
    justifyContent: 'flex-end',
    zIndex: 1000,
  },
  iosModal: {
    backgroundColor: colors.surface,
    borderTopLeftRadius: borderRadius.lg,
    borderTopRightRadius: borderRadius.lg,
    paddingBottom: spacing.lg,
  },
  iosHeader: {
    flexDirection: 'row',
    justifyContent: 'flex-end',
    padding: spacing.md,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  iosDoneButton: {
    fontSize: fontSize.md,
    fontWeight: '600',
    color: colors.primary,
  },
});
