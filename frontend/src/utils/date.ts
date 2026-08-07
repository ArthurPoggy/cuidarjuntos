/**
 * Pure date utilities for the "upcoming" agenda screen.
 *
 * All of these derive the calendar day from the DEVICE's local timezone,
 * never from UTC. `Date#toISOString()` always returns the UTC calendar
 * date, which is off by one near midnight in negative UTC-offset
 * timezones (e.g. America/Sao_Paulo, UTC-3) - that mismatch was the root
 * cause of the 'Hoje'/'Amanha' mislabeling bug in UpcomingScreen.
 */
import { format, addDays } from 'date-fns';

/** 'YYYY-MM-DD' date-fns format token. */
const DATE_ISO_FORMAT = 'yyyy-MM-dd';

/**
 * Returns the LOCAL calendar date (device timezone) for the given instant,
 * as a 'YYYY-MM-DD' string. Defaults to "now".
 */
export function getLocalDateIso(instant: Date = new Date()): string {
  return format(instant, DATE_ISO_FORMAT);
}

/**
 * Labels a bucket date (a 'YYYY-MM-DD' local calendar date string, e.g.
 * `bucket.date_iso` from the API) as 'Hoje', 'Amanha', or a weekday +
 * day/month string - always comparing against the LOCAL calendar date of
 * `now` (defaults to the current instant).
 */
export function formatDayLabel(dateIso: string, now: Date = new Date()): string {
  const todayIso = getLocalDateIso(now);
  const tomorrowIso = getLocalDateIso(addDays(now, 1));

  if (dateIso === todayIso) return 'Hoje';
  if (dateIso === tomorrowIso) return 'Amanha';

  const d = new Date(dateIso + 'T00:00:00');
  const weekdays = ['Domingo', 'Segunda', 'Terca', 'Quarta', 'Quinta', 'Sexta', 'Sabado'];
  const dayOfWeek = weekdays[d.getDay()];
  const day = String(d.getDate()).padStart(2, '0');
  const month = String(d.getMonth() + 1).padStart(2, '0');
  return `${dayOfWeek}, ${day}/${month}`;
}

/**
 * Builds the `from`/`to` range params sent to
 * `dashboardApi.upcomingBuckets`, anchored on the LOCAL calendar date of
 * `now` (defaults to the current instant) - matching the calendar day the
 * backend buckets under `date_iso` for "today".
 */
export function getUpcomingRangeParams(
  now: Date = new Date(),
  daysAhead: number = 7,
): { from: string; to: string } {
  return {
    from: getLocalDateIso(now),
    to: getLocalDateIso(addDays(now, daysAhead)),
  };
}
