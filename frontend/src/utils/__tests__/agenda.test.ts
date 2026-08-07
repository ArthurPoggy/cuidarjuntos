/**
 * Unit tests for task #100 item: "Refatorar UpcomingScreen.tsx extraindo
 * logica pura de montagem da lista (headers+itens) e status para funcoes
 * testaveis".
 *
 * `UpcomingScreen.tsx` currently builds its FlatList data (a flat array
 * that intercalates one 'header' entry per day bucket with one 'item'
 * entry per record in that bucket) inline in the component body, and
 * keeps the status -> color / status -> label lookup tables (with their
 * fallbacks) as component-local constants. None of that has any
 * dependency on React Native and should live in a plain, testable module.
 *
 * These tests target a pure utility module, `src/utils/agenda.ts`, that
 * the refactor is expected to introduce:
 *   - `buildAgendaEntries(buckets: UpcomingBucket[]): ListEntry[]`
 *   - `getStatusColor(status: string): string`
 *   - `getStatusLabel(status: string): string`
 *   - `STATUS_COLORS` / `STATUS_LABELS` lookup tables
 *
 * The module does not exist yet, so this whole suite is expected to fail
 * (module not found) against the current code. That is the intended
 * "red" state for this task: only tests are being added here, the
 * refactor itself (creating src/utils/agenda.ts and wiring it into
 * UpcomingScreen) is a separate step.
 */

import {
  buildAgendaEntries,
  getStatusColor,
  getStatusLabel,
  STATUS_COLORS,
  STATUS_LABELS,
} from '../agenda';
import type { UpcomingBucket, BucketItem } from '../../types/models';

function makeItem(overrides: Partial<BucketItem> = {}): BucketItem {
  return {
    id: 1,
    type: 'medication',
    title: 'Item',
    time: '08:00:00',
    who: 'Alice',
    status: 'pending',
    series: false,
    ...overrides,
  };
}

describe('buildAgendaEntries', () => {
  it('returns an empty array for an empty bucket list', () => {
    expect(buildAgendaEntries([])).toEqual([]);
  });

  it('returns an empty array when buckets have no items (no headers for empty days)', () => {
    const buckets: UpcomingBucket[] = [{ date_iso: '2026-08-04', items: [] }];
    // A day bucket with zero items should not still contribute a header
    // that is immediately followed by nothing useful to the user.
    expect(buildAgendaEntries(buckets)).toEqual([]);
  });

  it('emits one header followed by that day items, for a single day with multiple items, preserving order', () => {
    const item1 = makeItem({ id: 1, title: 'Primeiro' });
    const item2 = makeItem({ id: 2, title: 'Segundo' });
    const buckets: UpcomingBucket[] = [
      { date_iso: '2026-08-04', items: [item1, item2] },
    ];

    const entries = buildAgendaEntries(buckets);

    expect(entries).toHaveLength(3);
    expect(entries[0]).toMatchObject({
      kind: 'header',
      key: 'header-2026-08-04',
      dateIso: '2026-08-04',
    });
    expect(entries[1]).toMatchObject({
      kind: 'item',
      key: 'item-2026-08-04-1',
      dateIso: '2026-08-04',
      item: item1,
    });
    expect(entries[2]).toMatchObject({
      kind: 'item',
      key: 'item-2026-08-04-2',
      dateIso: '2026-08-04',
      item: item2,
    });
  });

  it('emits one header per day, each immediately followed by that day items, for multiple days', () => {
    const dayOneItem = makeItem({ id: 10, title: 'Dia 1' });
    const dayTwoItemA = makeItem({ id: 20, title: 'Dia 2 A' });
    const dayTwoItemB = makeItem({ id: 21, title: 'Dia 2 B' });
    const buckets: UpcomingBucket[] = [
      { date_iso: '2026-08-04', items: [dayOneItem] },
      { date_iso: '2026-08-05', items: [dayTwoItemA, dayTwoItemB] },
    ];

    const entries = buildAgendaEntries(buckets);

    expect(entries.map((e) => e.kind)).toEqual([
      'header',
      'item',
      'header',
      'item',
      'item',
    ]);
    expect(entries.map((e) => e.key)).toEqual([
      'header-2026-08-04',
      'item-2026-08-04-10',
      'header-2026-08-05',
      'item-2026-08-05-20',
      'item-2026-08-05-21',
    ]);
    // Every entry must carry the dateIso of the bucket it belongs to, so
    // downstream consumers never need to cross-reference back to `buckets`.
    expect(entries[0]).toMatchObject({ dateIso: '2026-08-04' });
    expect(entries[1]).toMatchObject({ dateIso: '2026-08-04' });
    expect(entries[2]).toMatchObject({ dateIso: '2026-08-05' });
    expect(entries[3]).toMatchObject({ dateIso: '2026-08-05' });
    expect(entries[4]).toMatchObject({ dateIso: '2026-08-05' });
  });

  it('produces unique keys across all entries, even with duplicate item ids in different days', () => {
    const buckets: UpcomingBucket[] = [
      { date_iso: '2026-08-04', items: [makeItem({ id: 1 })] },
      { date_iso: '2026-08-05', items: [makeItem({ id: 1 })] },
    ];

    const entries = buildAgendaEntries(buckets);
    const keys = entries.map((e) => e.key);

    expect(new Set(keys).size).toBe(keys.length);
  });
});

describe('status color/label helpers', () => {
  it.each([
    ['pending', STATUS_COLORS.pending, 'Pendente'],
    ['done', STATUS_COLORS.done, 'Feito'],
    ['missed', STATUS_COLORS.missed, 'Perdido'],
  ])('resolves color and label for known status %s', (status, expectedColor, expectedLabel) => {
    expect(getStatusColor(status)).toBe(expectedColor);
    expect(getStatusLabel(status)).toBe(expectedLabel);
    expect(STATUS_LABELS[status]).toBe(expectedLabel);
  });

  it('falls back to a default color for an unknown status, instead of undefined', () => {
    const color = getStatusColor('some-unmapped-status');
    expect(color).toBeTruthy();
    expect(color).not.toBe(STATUS_COLORS.pending);
    expect(color).not.toBe(STATUS_COLORS.done);
    expect(color).not.toBe(STATUS_COLORS.missed);
  });

  it('falls back to the raw status string as the label for an unknown status', () => {
    expect(getStatusLabel('some-unmapped-status')).toBe('some-unmapped-status');
  });
});
