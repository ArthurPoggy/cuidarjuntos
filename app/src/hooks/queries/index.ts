import { useQuery, useMutation, useQueryClient, useInfiniteQuery, type UseQueryOptions } from '@tanstack/react-query';
import {
  recordsApi, dashboardApi, medicationsApi,
  shiftsApi, checklistApi, chartsApi, adminApi, notificationsApi,
  type ChartKind, type ChartResponse,
} from '../../api/endpoints';
import type { CareRecord, DashboardData, Medication, Notification, PaginatedResponse } from '../../types/models';

function pageNumberFromUrl(url: string | null): number | undefined {
  if (!url) return undefined;
  try {
    const u = new URL(url);
    const page = u.searchParams.get('page');
    return page ? Number(page) : undefined;
  } catch {
    return undefined;
  }
}

// ---------- Query keys ----------
export const queryKeys = {
  records: (params?: Record<string, string>) => ['records', params] as const,
  record: (id: number) => ['records', id] as const,
  dashboard: (params?: Record<string, string>) => ['dashboard', params] as const,
  medications: (params?: Record<string, string>) => ['medications', params] as const,
  shifts: (params?: Record<string, string>) => ['shifts', params] as const,
  checklist: (params?: Record<string, string>) => ['checklist', params] as const,
  chart: (kind: ChartKind, params?: Record<string, string>) => ['charts', kind, params] as const,
  notifications: (params?: Record<string, string>) => ['notifications', params] as const,
  notificationsUnreadCount: () => ['notifications', 'unread-count'] as const,
};

// ---------- Records ----------
export function useRecords(
  params?: Record<string, string>,
  options?: Partial<UseQueryOptions<PaginatedResponse<CareRecord>>>
) {
  return useQuery({
    queryKey: queryKeys.records(params),
    queryFn: async () => (await recordsApi.list(params)).data,
    ...options,
  });
}

export function useInfiniteRecords(filter?: string) {
  return useInfiniteQuery({
    queryKey: ['records', 'infinite', filter ?? ''],
    initialPageParam: 1,
    queryFn: async ({ pageParam }) => {
      const params: Record<string, string> = { page: String(pageParam) };
      if (filter) params.type = filter;
      return (await recordsApi.list(params)).data;
    },
    getNextPageParam: (last) => pageNumberFromUrl(last.next),
  });
}

export function useRecord(id: number) {
  return useQuery({
    queryKey: queryKeys.record(id),
    queryFn: async () => (await recordsApi.get(id)).data,
    enabled: !!id,
  });
}

export function useSetRecordStatus() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...data }: { id: number; status: string; reason?: string; date?: string; time?: string }) =>
      recordsApi.setStatus(id, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['records'] });
      qc.invalidateQueries({ queryKey: ['dashboard'] });
    },
  });
}

export function useDeleteRecord() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => recordsApi.delete(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['records'] }),
  });
}

// ---------- Dashboard ----------
export function useDashboard(
  params?: Record<string, string>,
  options?: Partial<UseQueryOptions<DashboardData>>
) {
  return useQuery({
    queryKey: queryKeys.dashboard(params),
    queryFn: async () => (await dashboardApi.get(params)).data,
    ...options,
  });
}

export function useUpcomingBuckets(params?: Record<string, string>) {
  return useQuery({
    queryKey: ['upcoming-buckets', params ?? {}],
    queryFn: async () => (await dashboardApi.upcomingBuckets(params)).data,
  });
}

export function useBulkSetStatus() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: { ids: number[]; status: 'done' | 'missed'; date?: string; time?: string }) =>
      recordsApi.bulkSetStatus(data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['upcoming-buckets'] });
      qc.invalidateQueries({ queryKey: ['records'] });
      qc.invalidateQueries({ queryKey: ['dashboard'] });
    },
  });
}

export function useReactToRecord() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, reaction }: { id: number; reaction: string }) =>
      recordsApi.react(id, reaction),
    onSuccess: (_, { id }) => {
      qc.invalidateQueries({ queryKey: ['records', id] });
    },
  });
}

export function useAddComment() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, text }: { id: number; text: string }) =>
      recordsApi.addComment(id, text),
    onSuccess: (_, { id }) => {
      qc.invalidateQueries({ queryKey: ['records', id, 'comments'] });
      qc.invalidateQueries({ queryKey: ['records', id] });
    },
  });
}

export function useRecordComments(id: number) {
  return useQuery({
    queryKey: ['records', id, 'comments'],
    queryFn: async () => (await recordsApi.getComments(id)).data,
    enabled: !!id,
  });
}

export function useAdminOverview() {
  return useQuery({
    queryKey: ['admin', 'overview'],
    queryFn: async () => (await adminApi.overview()).data,
  });
}

// ---------- Shifts ----------
export function useCreateShift() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: Parameters<typeof shiftsApi.create>[0]) => shiftsApi.create(data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['shifts'] }),
  });
}

export function useDeleteShift() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => shiftsApi.delete(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['shifts'] }),
  });
}

export function useDeleteShiftSeries() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => shiftsApi.deleteSeries(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['shifts'] }),
  });
}

// ---------- Checklist ----------
export function useCreateChecklistItem() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: Parameters<typeof checklistApi.create>[0]) => checklistApi.create(data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['checklist'] }),
  });
}

export function useDeleteChecklistItem() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => checklistApi.delete(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['checklist'] }),
  });
}

// ---------- Medications ----------
export function useMedications(params?: Record<string, string>) {
  return useQuery({
    queryKey: queryKeys.medications(params),
    queryFn: async () => (await medicationsApi.list(params)).data,
  });
}

export function useStockOverview(search?: string) {
  const params = search ? { search } : undefined;
  return useQuery({
    queryKey: ['medications', 'stock', search ?? ''],
    queryFn: async () => (await medicationsApi.stockOverview(params)).data,
  });
}

export function useAddStock() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, quantity }: { id: number; quantity: number }) =>
      medicationsApi.addStock(id, quantity),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['medications'] }),
  });
}

export function useCreateMedication() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: { name: string; dosage: string }) => medicationsApi.create(data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['medications'] }),
  });
}

// ---------- Shifts ----------
export function useShifts(params?: Record<string, string>) {
  return useQuery({
    queryKey: queryKeys.shifts(params),
    queryFn: async () => (await shiftsApi.list(params)).data,
  });
}

// ---------- Checklist ----------
export function useChecklist(params?: Record<string, string>) {
  return useQuery({
    queryKey: queryKeys.checklist(params),
    queryFn: async () => (await checklistApi.list(params)).data,
  });
}

export function useToggleChecklist() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => checklistApi.toggle(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['checklist'] }),
  });
}

// ---------- Charts ----------
export function useChart(kind: ChartKind, params?: Record<string, string>) {
  return useQuery<ChartResponse>({
    queryKey: queryKeys.chart(kind, params),
    queryFn: async () => (await chartsApi.fetch(kind, params)).data,
  });
}

// ---------- Notifications ----------
export function useNotifications(params?: Record<string, string>) {
  return useQuery<PaginatedResponse<Notification>>({
    queryKey: queryKeys.notifications(params),
    queryFn: async () => (await notificationsApi.list(params)).data,
  });
}

export function useMarkNotificationRead() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => notificationsApi.markRead(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['notifications'] });
    },
  });
}

export function useMarkAllNotificationsRead() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => notificationsApi.markAllRead(),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['notifications'] });
    },
  });
}

/**
 * Retorna somente a contagem de notificações não lidas.
 * Polling a cada 60 s; invalida quando qualquer notificação é marcada como lida.
 */
export function useUnreadNotificationCount() {
  return useQuery<number>({
    queryKey: queryKeys.notificationsUnreadCount(),
    queryFn: async () => {
      const res = await notificationsApi.unreadCount();
      return res.data.count;
    },
    refetchInterval: 60_000,
    staleTime: 30_000,
  });
}
