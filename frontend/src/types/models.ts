// Enums matching Django model choices
export enum RecordType {
  MEDICATION = 'medication',
  MEAL = 'meal',
  VITAL = 'vital',
  ACTIVITY = 'activity',
  PROGRESS = 'progress',
  SLEEP = 'sleep',
  BATHROOM = 'bathroom',
  OTHER = 'other',
}

export enum RecordStatus {
  PENDING = 'pending',
  DONE = 'done',
  MISSED = 'missed',
}

export enum Recurrence {
  NONE = 'none',
  DAILY = 'daily',
  WEEKLY = 'weekly',
  MONTHLY = 'monthly',
}

export enum ProgressTrend {
  EVOLUTION = 'evolution',
  REGRESSION = 'regression',
}

export enum ReactionType {
  HEART = 'heart',
  CLAP = 'clap',
  PRAY = 'pray',
}

export enum RelationToPatient {
  SELF = 'SELF',
  FAMILY = 'FAMILY',
  DOCTOR = 'DOCTOR',
  CAREGIVER = 'CAREGIVER',
  OTHER = 'OTHER',
}

// Model interfaces
export interface Profile {
  role: string;
  full_name: string;
  birth_date: string | null;
  cpf: string;
}

export interface MembershipBrief {
  group_id: number;
  group_name: string;
  patient_name: string;
  relation_to_patient: string;
}

export interface User {
  id: number;
  username: string;
  email: string;
  first_name: string;
  last_name: string;
  profile: Profile;
  membership: MembershipBrief | null;
}

export interface Patient {
  id: number;
  name: string;
  birth_date: string | null;
  notes: string;
}

export interface CareGroup {
  id: number;
  name: string;
  patient: Patient;
  member_count: number;
  created_at: string;
}

export interface GroupMembership {
  id: number;
  username: string;
  group_name: string;
  relation_to_patient: string;
}

export interface Medication {
  id: number;
  name: string;
  dosage: string;
  created_at: string;
}

export interface MedicationWithStock extends Medication {
  current_stock: number;
  status: 'danger' | 'warn' | 'ok';
}

export interface SocialSummary {
  counts: Record<string, number>;
  user_reaction: string;
  comments_count: number;
}

export interface CareRecord {
  id: number;
  patient: number;
  type: RecordType;
  what: string;
  description: string;
  medication: number | null;
  capsule_quantity: number | null;
  progress_trend: string;
  missed_reason: string;
  is_exception: boolean;
  date: string;
  time: string;
  recurrence: Recurrence;
  repeat_until: string | null;
  status: RecordStatus;
  caregiver: string;
  created_by: number | null;
  timestamp: string;
  recurrence_group: string | null;
  author_name: string;
  medication_detail: string;
  is_from_series: boolean;
  social: SocialSummary;
}

export interface RecordReaction {
  id: number;
  reaction: ReactionType;
  username: string;
  created_at: string;
}

export interface RecordComment {
  id: number;
  text: string;
  author: string;
  created_at: string;
}

export interface Tokens {
  access: string;
  refresh: string;
}

// API response types
export interface PaginatedResponse<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

export interface DashboardData {
  counts: Record<string, number>;
  records: CareRecord[];
  upcoming: CareRecord[];
  filters: {
    start: string | null;
    end: string | null;
    categories: string[];
    exceptions: boolean;
    count_done_only: boolean;
  };
}

export interface CalendarData {
  year: number;
  month: number;
  month_name: string;
  weeks: number[][];
  days_with: number[];
  today_iso: string;
  events_by_date: Record<string, CalendarEvent[]>;
}

export interface CalendarEvent {
  type: string;
  title: string;
  what: string;
  time: string;
  who: string;
}

export interface UpcomingBucket {
  date_iso: string;
  items: BucketItem[];
}

export interface BucketItem {
  id: number;
  type: string;
  title: string;
  time: string;
  who: string;
  status: string;
  series: boolean;
}

export interface StockSection {
  key: string;
  title: string;
  items: MedicationWithStock[];
}
