import React, { useEffect, useRef, useState } from 'react';
import { Animated, TouchableOpacity, ActivityIndicator, StyleSheet, Text } from 'react-native';
import Svg, { Path } from 'react-native-svg';
import { colors, borderRadius } from '../theme';
import { useSpeechToText } from '../hooks/useSpeechToText';

interface Props {
  onResult: (text: string) => void;
  onError?: (err: unknown) => void;
  size?: number;
}

function MicIcon({ color, size }: { color: string; size: number }) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <Path
        d="M12 15a3 3 0 003-3V6a3 3 0 00-6 0v6a3 3 0 003 3z"
        stroke={color}
        strokeWidth={2}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <Path
        d="M19 10v2a7 7 0 01-14 0v-2M12 19v3"
        stroke={color}
        strokeWidth={2}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </Svg>
  );
}

/**
 * Botão de microfone com feedback visual por estado:
 * idle (microfone neutro), recording (pulso vermelho), processing (spinner)
 * e error (aviso que volta a idle após 2s). Toque alterna gravar/parar.
 */
export default function MicrophoneButton({ onResult, onError, size = 24 }: Props) {
  const { status, isRecording, start, stop } = useSpeechToText(onError);
  const pulse = useRef(new Animated.Value(1)).current;
  const [showError, setShowError] = useState(false);

  useEffect(() => {
    if (status === 'recording') {
      const loop = Animated.loop(
        Animated.sequence([
          Animated.timing(pulse, { toValue: 1.25, duration: 600, useNativeDriver: true }),
          Animated.timing(pulse, { toValue: 1, duration: 600, useNativeDriver: true }),
        ])
      );
      loop.start();
      return () => loop.stop();
    }
    pulse.setValue(1);
    return undefined;
  }, [status, pulse]);

  useEffect(() => {
    if (status === 'error') {
      setShowError(true);
      const timer = setTimeout(() => setShowError(false), 2000);
      return () => clearTimeout(timer);
    }
    setShowError(false);
    return undefined;
  }, [status]);

  const handlePress = () => {
    if (isRecording) {
      void stop();
    } else {
      void start(onResult);
    }
  };

  const containerStyle = [
    styles.button,
    { width: size + 20, height: size + 20, borderRadius: borderRadius.full },
    isRecording && styles.recording,
    showError && styles.error,
  ];

  return (
    <TouchableOpacity onPress={handlePress} activeOpacity={0.7} accessibilityLabel="Gravar voz">
      <Animated.View style={[containerStyle, { transform: [{ scale: pulse }] }]}>
        {status === 'processing' ? (
          <ActivityIndicator size="small" color={colors.primary} />
        ) : showError ? (
          <Text style={[styles.warning, { fontSize: size }]}>!</Text>
        ) : (
          <MicIcon color={isRecording ? colors.textInverse : colors.textSecondary} size={size} />
        )}
      </Animated.View>
    </TouchableOpacity>
  );
}

const styles = StyleSheet.create({
  button: {
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: colors.borderLight,
  },
  recording: { backgroundColor: colors.danger },
  error: { backgroundColor: colors.borderLight, borderWidth: 1, borderColor: colors.danger },
  warning: { color: colors.danger, fontWeight: '700' },
});
