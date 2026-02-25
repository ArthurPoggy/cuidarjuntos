import client from './client';
import type {
  User, Tokens, CareGroup, CareRecord, Medication,
  MedicationWithStock, RecordComment, DashboardData,
  CalendarData, UpcomingBucket, PaginatedResponse, StockSection,
} from '../types/models';

// Auth
export const authApi = {
  register: (data: {
    full_name: string; cpf: string; birth_date?: string;
    email: string; username: string; password: string;
  }) => client.post<{ user: User; tokens: Tokens }>('/auth/register/', data),

  login: (username: string, password: string) =>
    client.post<Tokens>('/auth/token/', { username, password }),

  refreshToken: (refresh: string) =>
    client.post<{ access: string; refresh?: string }>('/auth/token/refresh/', { refresh }),

  me: () => client.get<User>('/auth/me/'),
};

// Groups
export const groupsApi = {
  list: () => client.get<CareGroup[]>('/groups/'),

  create: (data: {
    group_name: string; patient_name: string; patient_birth_date?: string;
    relation_to_patient: string; health_data?: string; group_pin: string;
  }) => client.post<CareGroup>('/groups/create/', data),

  join: (data: { group_id: number; relation_to_patient: string; pin: string }) =>
    client.post<CareGroup>('/groups/join/', data),

  leave: () => client.post('/groups/leave/'),

  current: () => client.get<{ group: CareGroup | null; membership?: { relation_to_patient: string } }>('/groups/current/'),
};

// Records
export const recordsApi = {
  list: (params?: Record<string, string>) =>
    client.get<PaginatedResponse<CareRecord>>('/records/', { params }),

  create: (data: Partial<CareRecord> & Record<string, unknown>) =>
    client.post<CareRecord>('/records/', data),

  get: (id: number) => client.get<CareRecord>(`/records/${id}/`),

  update: (id: number, data: Partial<CareRecord> & Record<string, unknown>) =>
    client.patch<CareRecord>(`/records/${id}/`, data),

  delete: (id: number) => client.delete(`/records/${id}/`),

  setStatus: (id: number, data: { status: string; reason?: string; date?: string; time?: string }) =>
    client.post(`/records/${id}/set_status/`, data),

  react: (id: number, reaction: string) =>
    client.post(`/records/${id}/react/`, { reaction }),

  getComments: (id: number) =>
    client.get<RecordComment[]>(`/records/${id}/comments/`),

  addComment: (id: number, text: string) =>
    client.post<RecordComment>(`/records/${id}/comments/`, { text }),

  cancelFollowing: (id: number) =>
    client.post(`/records/${id}/cancel_following/`),

  bulkSetStatus: (data: { ids: number[]; status: string; date?: string; time?: string }) =>
    client.post('/records/bulk_set_status/', data),

  reschedule: (data: { id: number; date: string; time: string }) =>
    client.post('/records/reschedule/', data),
};

// Dashboard / Calendar / Upcoming
export const dashboardApi = {
  get: (params?: Record<string, string>) =>
    client.get<DashboardData>('/dashboard/', { params }),

  calendar: (params?: Record<string, string>) =>
    client.get<CalendarData>('/calendar/', { params }),

  upcoming: (params?: Record<string, string>) =>
    client.get<{ ok: boolean; items: CareRecord[] }>('/upcoming/', { params }),

  upcomingBuckets: (params?: Record<string, string>) =>
    client.get<{ ok: boolean; buckets: UpcomingBucket[]; totals: Record<string, number> }>(
      '/upcoming/buckets/', { params }
    ),

  exportCsv: (params?: Record<string, string>) =>
    client.get('/export/csv/', { params, responseType: 'blob' }),
};

// Medications
export const medicationsApi = {
  list: (params?: Record<string, string>) =>
    client.get<PaginatedResponse<Medication>>('/medications/', { params }),

  create: (data: { name: string; dosage: string }) =>
    client.post<Medication>('/medications/', data),

  update: (id: number, data: { name?: string; dosage?: string }) =>
    client.patch<Medication>(`/medications/${id}/`, data),

  delete: (id: number) => client.delete(`/medications/${id}/`),

  addStock: (id: number, quantity: number) =>
    client.post(`/medications/${id}/add_stock/`, { quantity }),

  stockOverview: (params?: Record<string, string>) =>
    client.get<{ sections: StockSection[] }>('/medications/stock_overview/', { params }),
};

// Admin
export const adminApi = {
  overview: (params?: Record<string, string>) =>
    client.get('/admin/overview/', { params }),
};
