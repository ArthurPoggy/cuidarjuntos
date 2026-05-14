import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import type { CareRecord } from '../types/models';

export type AuthStackParamList = {
  Login: undefined;
  Register: undefined;
  PasswordReset: undefined;
  Settings: undefined;
};

export type GroupStackParamList = {
  ChooseGroup: undefined;
  CreateGroup: undefined;
  JoinGroup: undefined;
};

export type MainStackParamList = {
  Dashboard: undefined;
  Records: { filter?: string } | undefined;
  RecordCreate: { record?: CareRecord; type?: string } | undefined;
  RecordDetail: { recordId: number };
  Medications: undefined;
  Upcoming: undefined;
  Shifts: undefined;
  Checklist: undefined;
  Charts: undefined;
  Export: undefined;
  Profile: undefined;
  AdminOverview: undefined;
  Notifications: undefined;
};

export type RootStackParamList = AuthStackParamList & GroupStackParamList & MainStackParamList;

export type AuthScreenProps<T extends keyof AuthStackParamList> =
  NativeStackScreenProps<AuthStackParamList, T>;

export type GroupScreenProps<T extends keyof GroupStackParamList> =
  NativeStackScreenProps<GroupStackParamList, T>;

export type MainScreenProps<T extends keyof MainStackParamList> =
  NativeStackScreenProps<MainStackParamList, T>;
