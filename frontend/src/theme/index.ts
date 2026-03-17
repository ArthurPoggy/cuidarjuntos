export const colors = {
  // Cor principal do CuidarJuntos (igual ao web)
  primary: '#2563EB',        // blue-600 Tailwind (CORRIGIDO!)
  primaryDark: '#1E40AF',    // blue-700
  primaryLight: '#3B82F6',   // blue-500
  secondary: '#6366F1',
  success: '#22C55E',
  warning: '#EAB308',
  danger: '#EF4444',
  info: '#06B6D4',

  // Backgrounds (igual ao web)
  background: '#F9FAFB',     // gray-50
  surface: '#FFFFFF',
  card: '#FFFFFF',

  text: '#111827',           // gray-900
  textSecondary: '#6B7280',  // gray-500
  textMuted: '#9CA3AF',      // gray-400
  textInverse: '#FFFFFF',

  border: '#E5E7EB',         // gray-200
  borderLight: '#F3F4F6',    // gray-100
  divider: '#E5E7EB',

  statusPending: '#F59E0B',  // amber-500
  statusDone: '#22C55E',     // green-500
  statusMissed: '#EF4444',   // red-500

  stockDanger: '#EF4444',
  stockWarn: '#F59E0B',
  stockOk: '#22C55E',
};

export const spacing = {
  xs: 4,
  sm: 8,
  md: 16,
  lg: 24,
  xl: 32,
  xxl: 48,
};

export const borderRadius = {
  sm: 6,
  md: 10,
  lg: 16,
  xl: 24,
  full: 9999,
};

export const fontSize = {
  xs: 12,
  sm: 14,
  md: 16,
  lg: 18,
  xl: 22,
  xxl: 28,
  title: 32,
};

export const fontWeight = {
  regular: '400' as const,
  medium: '500' as const,
  semibold: '600' as const,
  bold: '700' as const,
};
