/**
 * Hook that owns the navigable date range ("from"/"to") for the Agenda
 * ("upcoming") screen, decoupled from the screen component itself so it can
 * be tested in isolation and reused elsewhere.
 *
 * The range is always `windowDays` days wide (default 7, matching the
 * backend's default window in `api/views/care.py::upcoming_buckets`). The
 * hook keeps an internal "anchor" date (the current `from`) and exposes
 * actions to shift it by a week or a calendar month, always preserving the
 * window length and composing on top of the current anchor (not the
 * original base date).
 */
import { useCallback, useMemo, useState } from 'react';
import { addDays, addMonths, subDays, subMonths } from 'date-fns';
import { getUpcomingRangeParams } from '../utils/date';

export interface AgendaRange {
  /** Start of the range, local calendar date, 'YYYY-MM-DD'. */
  from: string;
  /** End of the range, local calendar date, 'YYYY-MM-DD'. */
  to: string;
  /** Shift the range forward by 7 days, preserving its length. */
  goToNextWeek: () => void;
  /** Shift the range backward by 7 days, preserving its length. */
  goToPreviousWeek: () => void;
  /** Shift the anchor forward by 1 calendar month, preserving the window length. */
  goToNextMonth: () => void;
  /** Shift the anchor backward by 1 calendar month, preserving the window length. */
  goToPreviousMonth: () => void;
}

/**
 * @param baseDate  Instant that seeds the initial anchor ("from"). Defaults to "now".
 * @param windowDays Width of the range in days. Defaults to 7 (today .. today+7).
 */
export function useAgendaRange(baseDate: Date = new Date(), windowDays: number = 7): AgendaRange {
  const [anchor, setAnchor] = useState<Date>(baseDate);

  const goToNextWeek = useCallback(() => {
    setAnchor((prev) => addDays(prev, 7));
  }, []);

  const goToPreviousWeek = useCallback(() => {
    setAnchor((prev) => subDays(prev, 7));
  }, []);

  const goToNextMonth = useCallback(() => {
    setAnchor((prev) => addMonths(prev, 1));
  }, []);

  const goToPreviousMonth = useCallback(() => {
    setAnchor((prev) => subMonths(prev, 1));
  }, []);

  return useMemo(
    () => ({
      ...getUpcomingRangeParams(anchor, windowDays),
      goToNextWeek,
      goToPreviousWeek,
      goToNextMonth,
      goToPreviousMonth,
    }),
    [anchor, windowDays, goToNextWeek, goToPreviousWeek, goToNextMonth, goToPreviousMonth],
  );
}
