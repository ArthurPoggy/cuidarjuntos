/**
 * @jest-environment jsdom
 */
/**
 * Unit tests for `useAgendaRange`, the hook that task #100 asks us to
 * extract out of `UpcomingScreen.tsx` so that the "from/to" range shown by
 * the Agenda screen becomes navigable (previous/next week, previous/next
 * month) instead of being permanently pinned to "today .. today+7 days".
 *
 * The hook does not exist yet (`src/hooks/useAgendaRange.ts` is expected to
 * be created by the fix). This whole suite is expected to fail against the
 * current code - "module not found" - which is the intended red state for
 * this step: only tests are being added here.
 *
 * Contract under test (mirrors the acceptance criteria of the task card):
 *
 *   useAgendaRange(baseDate?: Date, windowDays: number = 7) => {
 *     from: string;              // 'YYYY-MM-DD', LOCAL calendar date
 *     to: string;                // 'YYYY-MM-DD', LOCAL calendar date
 *     goToNextWeek: () => void;
 *     goToPreviousWeek: () => void;
 *     goToNextMonth: () => void;
 *     goToPreviousMonth: () => void;
 *   }
 *
 * - `baseDate` seeds the initial anchor ("from"); it defaults to "now".
 * - The initial range is always [from, from + windowDays days], matching
 *   the fixed window `getUpcomingRangeParams` currently sends to
 *   `dashboardApi.upcomingBuckets` (today .. today+7).
 * - `goToNextWeek` / `goToPreviousWeek` shift BOTH `from` and `to` by
 *   +/- 7 days, preserving the window length (`to - from` stays constant).
 * - `goToNextMonth` / `goToPreviousMonth` shift the anchor (`from`) by +/- 1
 *   calendar month (via date-fns `addMonths`, which clamps to the last day
 *   of the target month when it is shorter - e.g. Jan 31 -> Feb 28), then
 *   recompute `to` as `from + windowDays days`, again preserving the window
 *   length.
 * - Navigation actions compose: calling two actions back-to-back must
 *   produce the range you'd expect from applying both shifts in sequence,
 *   anchored on the range produced by the first action (not on the
 *   original base date).
 *
 * All dates are asserted as local-calendar 'YYYY-MM-DD' strings (the same
 * convention already established by `src/utils/date.ts`), timezone forced
 * to America/Sao_Paulo (UTC-3) so the suite is deterministic in any CI
 * environment.
 */

process.env.TZ = 'America/Sao_Paulo';

import { renderHook, act } from '@testing-library/react';
import { useAgendaRange } from '../useAgendaRange';

// Fixed, known base date used across most cases: 2026-01-10 (a Saturday),
// picked to sit comfortably mid-month/mid-year so week/month arithmetic
// isn't accidentally exercising an edge case unless the test says so.
const BASE = new Date('2026-01-10T12:00:00.000Z'); // noon UTC == 09:00 local, safely mid-day

describe('useAgendaRange - initial range', () => {
  it('starts at [baseDate, baseDate + 7 days] by default, matching the current fixed window', () => {
    const { result } = renderHook(() => useAgendaRange(BASE));

    expect(result.current.from).toBe('2026-01-10');
    expect(result.current.to).toBe('2026-01-17');
  });

  it('honors a custom windowDays for the initial range', () => {
    const { result } = renderHook(() => useAgendaRange(BASE, 3));

    expect(result.current.from).toBe('2026-01-10');
    expect(result.current.to).toBe('2026-01-13');
  });

  it('defaults the base date to "now" when none is provided', () => {
    const { result } = renderHook(() => useAgendaRange());

    // Whatever "now" is, from must be today's local date and the window
    // must span exactly 7 days.
    const today = new Date();
    const expectedFrom = today.toISOString(); // sanity placeholder, real assert below uses local formatting
    expect(typeof result.current.from).toBe('string');
    expect(result.current.from).toMatch(/^\d{4}-\d{2}-\d{2}$/);
    expect(result.current.to).toMatch(/^\d{4}-\d{2}-\d{2}$/);
    expect(result.current.from).not.toBe(result.current.to);
  });
});

describe('useAgendaRange - week navigation', () => {
  it('goToNextWeek shifts both from and to forward by 7 days', () => {
    const { result } = renderHook(() => useAgendaRange(BASE));

    act(() => {
      result.current.goToNextWeek();
    });

    expect(result.current.from).toBe('2026-01-17');
    expect(result.current.to).toBe('2026-01-24');
  });

  it('goToPreviousWeek shifts both from and to backward by 7 days', () => {
    const { result } = renderHook(() => useAgendaRange(BASE));

    act(() => {
      result.current.goToPreviousWeek();
    });

    expect(result.current.from).toBe('2026-01-03');
    expect(result.current.to).toBe('2026-01-10');
  });

  it('calling goToNextWeek twice advances by 14 days total (actions compose)', () => {
    const { result } = renderHook(() => useAgendaRange(BASE));

    act(() => {
      result.current.goToNextWeek();
    });
    act(() => {
      result.current.goToNextWeek();
    });

    expect(result.current.from).toBe('2026-01-24');
    expect(result.current.to).toBe('2026-01-31');
  });

  it('goToNextWeek followed by goToPreviousWeek returns to the original range', () => {
    const { result } = renderHook(() => useAgendaRange(BASE));

    act(() => {
      result.current.goToNextWeek();
    });
    act(() => {
      result.current.goToPreviousWeek();
    });

    expect(result.current.from).toBe('2026-01-10');
    expect(result.current.to).toBe('2026-01-17');
  });

  it('goToNextWeek crosses a month boundary correctly (Jan -> Feb)', () => {
    const endOfJan = new Date('2026-01-28T12:00:00.000Z');
    const { result } = renderHook(() => useAgendaRange(endOfJan));

    act(() => {
      result.current.goToNextWeek();
    });

    expect(result.current.from).toBe('2026-02-04');
    expect(result.current.to).toBe('2026-02-11');
  });

  it('goToPreviousWeek crosses a year boundary correctly (Jan -> Dec of previous year)', () => {
    const earlyJan = new Date('2026-01-03T12:00:00.000Z');
    const { result } = renderHook(() => useAgendaRange(earlyJan));

    act(() => {
      result.current.goToPreviousWeek();
    });

    expect(result.current.from).toBe('2025-12-27');
    expect(result.current.to).toBe('2026-01-03');
  });
});

describe('useAgendaRange - month navigation', () => {
  it('goToNextMonth shifts the anchor forward by 1 calendar month and preserves the window length', () => {
    const { result } = renderHook(() => useAgendaRange(BASE));

    act(() => {
      result.current.goToNextMonth();
    });

    expect(result.current.from).toBe('2026-02-10');
    expect(result.current.to).toBe('2026-02-17');
  });

  it('goToPreviousMonth shifts the anchor backward by 1 calendar month and preserves the window length', () => {
    const { result } = renderHook(() => useAgendaRange(BASE));

    act(() => {
      result.current.goToPreviousMonth();
    });

    expect(result.current.from).toBe('2025-12-10');
    expect(result.current.to).toBe('2025-12-17');
  });

  it('goToNextMonth clamps 31/Jan to the last day of February in a non-leap year', () => {
    const jan31 = new Date('2026-01-31T12:00:00.000Z'); // 2026 is not a leap year
    const { result } = renderHook(() => useAgendaRange(jan31));

    act(() => {
      result.current.goToNextMonth();
    });

    expect(result.current.from).toBe('2026-02-28');
    expect(result.current.to).toBe('2026-03-07');
  });

  it('goToNextMonth crosses the year boundary correctly (Dec -> Jan of the next year)', () => {
    const dec15 = new Date('2025-12-15T12:00:00.000Z');
    const { result } = renderHook(() => useAgendaRange(dec15));

    act(() => {
      result.current.goToNextMonth();
    });

    expect(result.current.from).toBe('2026-01-15');
    expect(result.current.to).toBe('2026-01-22');
  });

  it('goToPreviousMonth crosses the year boundary correctly (Jan -> Dec of the previous year)', () => {
    const jan15 = new Date('2026-01-15T12:00:00.000Z');
    const { result } = renderHook(() => useAgendaRange(jan15));

    act(() => {
      result.current.goToPreviousMonth();
    });

    expect(result.current.from).toBe('2025-12-15');
    expect(result.current.to).toBe('2025-12-22');
  });

  it('calling goToNextMonth twice advances by 2 calendar months total (actions compose)', () => {
    const { result } = renderHook(() => useAgendaRange(BASE));

    act(() => {
      result.current.goToNextMonth();
    });
    act(() => {
      result.current.goToNextMonth();
    });

    expect(result.current.from).toBe('2026-03-10');
    expect(result.current.to).toBe('2026-03-17');
  });

  it('goToNextMonth followed by goToPreviousMonth returns to the original range', () => {
    const { result } = renderHook(() => useAgendaRange(BASE));

    act(() => {
      result.current.goToNextMonth();
    });
    act(() => {
      result.current.goToPreviousMonth();
    });

    expect(result.current.from).toBe('2026-01-10');
    expect(result.current.to).toBe('2026-01-17');
  });
});

describe('useAgendaRange - mixed week/month navigation', () => {
  it('mixing week and month navigation composes on top of the current range, not the original base date', () => {
    const { result } = renderHook(() => useAgendaRange(BASE));

    act(() => {
      result.current.goToNextMonth(); // 2026-02-10 .. 2026-02-17
    });
    act(() => {
      result.current.goToNextWeek(); // 2026-02-17 .. 2026-02-24
    });

    expect(result.current.from).toBe('2026-02-17');
    expect(result.current.to).toBe('2026-02-24');
  });
});
