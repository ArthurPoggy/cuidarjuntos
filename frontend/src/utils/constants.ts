import { RecordType, ReactionType } from '../types/models';
import AsyncStorage from '@react-native-async-storage/async-storage';

// URL do backend (ngrok)
const BACKEND_URL = 'https://8731-179-127-127-253.ngrok-free.app';

// Função para obter API URL (com suporte a IP customizado)
export const getApiBaseUrl = async (): Promise<string> => {
  try {
    const customIP = await AsyncStorage.getItem('custom_api_ip');
    if (customIP) {
      return `http://${customIP}:8000/api/v1`;
    }
  } catch {}
  return `${BACKEND_URL}/api/v1`;
};

// URL síncrona
export const API_BASE_URL = `${BACKEND_URL}/api/v1`;

export interface CategoryMeta {
  label: string;
  icon: string;
  color: string;
  bg: string;
}

export const CATEGORY_META: Record<string, CategoryMeta> = {
  [RecordType.MEDICATION]: { label: 'Remédio', icon: '💊', color: '#3B82F6', bg: '#EFF6FF' },
  [RecordType.SLEEP]:      { label: 'Sono', icon: '🌙', color: '#8B5CF6', bg: '#F5F3FF' },
  [RecordType.MEAL]:       { label: 'Alimentação', icon: '🍽️', color: '#22C55E', bg: '#F0FDF4' },
  [RecordType.BATHROOM]:   { label: 'Banheiro', icon: '🚽', color: '#EAB308', bg: '#FEFCE8' },
  [RecordType.ACTIVITY]:   { label: 'Exercício', icon: '🏃', color: '#F97316', bg: '#FFF7ED' },
  [RecordType.VITAL]:      { label: 'Sinais Vitais', icon: '❤️', color: '#EF4444', bg: '#FEF2F2' },
  [RecordType.PROGRESS]:   { label: 'Evolução', icon: '📈', color: '#6366F1', bg: '#EEF2FF' },
  [RecordType.OTHER]:      { label: 'Outros', icon: '📝', color: '#EC4899', bg: '#FDF2F8' },
};

export const RECORD_TYPES = Object.values(RecordType);

export const REACTION_OPTIONS = [
  { code: ReactionType.HEART, emoji: '\u2764\uFE0F', label: 'Carinho' },
  { code: ReactionType.CLAP, emoji: '\uD83D\uDC4F', label: 'Reconhecimento' },
  { code: ReactionType.PRAY, emoji: '\uD83D\uDE4F', label: 'Forca' },
];

export const OTHER_VALUE = '__other__';

export const VITAL_KIND_CHOICES = [
  'Pressão arterial (PA)',
  'Frequência cardíaca (FrC)',
  'SpO2 (Oxímetro)',
  'Temperatura',
  OTHER_VALUE,
];

export const VITAL_STATUS_CHOICES = [
  'Normal', 'Hipertenso', 'Hipotenso', 'Febre',
  'Hipotermia', 'Taquicardia', 'Bradicardia', 'Baixa saturação',
  OTHER_VALUE,
];

export const BATHROOM_TYPE_CHOICES = [
  'Urina', 'Evacuação', 'Banho', 'Vômito', 'Higienização oral',
  OTHER_VALUE,
];

export const MEAL_TYPE_CHOICES = [
  'Café da manhã', 'Lanche da manhã', 'Almoço',
  'Lanche da tarde', 'Jantar', 'Ceia da noite',
  OTHER_VALUE,
];

export const MEAL_ACCEPTANCE_CHOICES = [
  'Boa aceitação', 'Ruim aceitação',
  OTHER_VALUE,
];

export const SLEEP_EVENT_CHOICES = [
  'dormiu', 'acordou',
  OTHER_VALUE,
];

export const PROGRESS_TREND_CHOICES = [
  'evolution', 'regression',
  OTHER_VALUE,
];

export const RELATION_CHOICES = [
  { value: 'SELF', label: 'Sou o paciente' },
  { value: 'FAMILY', label: 'Familiar' },
  { value: 'DOCTOR', label: 'Medico' },
  { value: 'CAREGIVER', label: 'Cuidador' },
  { value: 'OTHER', label: 'Outro' },
];
