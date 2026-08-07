import { colors } from '../theme';
import { formatDayLabel } from './date';
import type { UpcomingBucket, BucketItem } from '../types/models';

export const STATUS_COLORS: Record<string, string> = {
  pending: colors.statusPending,
  done: colors.statusDone,
  missed: colors.statusMissed,
};

export const STATUS_LABELS: Record<string, string> = {
  pending: 'Pendente',
  done: 'Feito',
  missed: 'Perdido',
};

export function getStatusColor(status: string): string {
  return STATUS_COLORS[status] ?? colors.textMuted;
}

export function getStatusLabel(status: string): string {
  return STATUS_LABELS[status] ?? status;
}

export type ListEntry =
  | { kind: 'header'; key: string; dateIso: string; dayLabel: string }
  | { kind: 'item'; key: string; item: BucketItem; dateIso: string };

/**
 * Flattens agenda buckets (one per day) into a single list of entries
 * suitable for a flat list: a header entry for the day followed by one
 * item entry per record in that day. Days with no items are omitted
 * entirely (no dangling header).
 */
export function buildAgendaEntries(buckets: UpcomingBucket[]): ListEntry[] {
  const entries: ListEntry[] = [];

  for (const bucket of buckets) {
    if (bucket.items.length === 0) continue;

    entries.push({
      kind: 'header',
      key: `header-${bucket.date_iso}`,
      dateIso: bucket.date_iso,
      dayLabel: formatDayLabel(bucket.date_iso),
    });

    for (const item of bucket.items) {
      entries.push({
        kind: 'item',
        key: `item-${bucket.date_iso}-${item.id}`,
        item,
        dateIso: bucket.date_iso,
      });
    }
  }

  return entries;
}
