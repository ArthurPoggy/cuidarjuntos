/**
 * Regression tests for the timezone bug described in task #100:
 *
 * `UpcomingScreen.formatDayLabel()` compares a local calendar date
 * (`dateIso`, e.g. bucket.date_iso, a 'YYYY-MM-DD' string with no time
 * component) against `today.toISOString().slice(0, 10)`, which is the
 * calendar date in UTC, not in the device's local timezone. In negative
 * UTC-offset timezones (e.g. America/Sao_Paulo, UTC-3) this produces wrong
 * 'Hoje'/'Amanha' labels - and, more importantly, can shift which day a
 * bucket is considered "today" for - whenever local time is late at night
 * but UTC has already rolled over to the next calendar day.
 *
 * These tests target a pure utility module, `src/utils/date.ts`, that the
 * fix is expected to introduce. It must always derive "today" from the
 * device's *local* calendar date (e.g. via date-fns), both for day-bucket
 * labelling and for the from/to params sent to `dashboardApi.upcomingBuckets`.
 *
 * The module does not exist yet, so this whole suite is expected to fail
 * (module not found) against the current code. That is the intended
 * "red" state for this task: only tests are being added here, the fix
 * itself (creating src/utils/date.ts and wiring it into UpcomingScreen)
 * is a separate step.
 */

// Force a negative-offset timezone regardless of the machine running the
// tests, so the bug reproduces deterministically in CI as well as locally.
process.env.TZ = 'America/Sao_Paulo'; // UTC-3, no DST

import { getLocalDateIso, formatDayLabel, getUpcomingRangeParams } from '../date';

describe('getLocalDateIso', () => {
  it('returns the LOCAL calendar date, not the UTC calendar date, near midnight in a negative-offset timezone', () => {
    // 2026-08-05T02:30:00Z is 2026-08-04T23:30:00 in America/Sao_Paulo
    // (UTC-3): local calendar day is still the 4th, UTC calendar day is
    // already the 5th.
    const instant = new Date('2026-08-05T02:30:00.000Z');

    expect(getLocalDateIso(instant)).toBe('2026-08-04');
    // Sanity check that this instant really does straddle the UTC/local
    // day boundary, i.e. that the test is actually exercising the bug.
    expect(instant.toISOString().slice(0, 10)).toBe('2026-08-05');
  });

  it('matches the local date for an instant safely in the middle of the local day', () => {
    // 2026-08-04T15:00:00Z is 2026-08-04T12:00:00 local (America/Sao_Paulo).
    const instant = new Date('2026-08-04T15:00:00.000Z');
    expect(getLocalDateIso(instant)).toBe('2026-08-04');
  });
});

describe('formatDayLabel', () => {
  it('labels the bucket for "today" as Hoje using the LOCAL calendar day, even right after UTC midnight', () => {
    // System clock: 2026-08-04T23:45:00 local (America/Sao_Paulo) ==
    // 2026-08-05T02:45:00Z. UTC has already rolled over to the 5th, but
    // locally it is still the 4th.
    const now = new Date('2026-08-05T02:45:00.000Z');

    // The bucket the API/backend would return for "today" is the LOCAL
    // calendar day: '2026-08-04'.
    const todayBucketDateIso = getLocalDateIso(now);
    expect(todayBucketDateIso).toBe('2026-08-04');

    expect(formatDayLabel(todayBucketDateIso, now)).toBe('Hoje');
  });

  it('labels the following LOCAL calendar day as Amanha, not the UTC day after', () => {
    const now = new Date('2026-08-05T02:45:00.000Z'); // local: 2026-08-04T23:45:00
    const tomorrowDateIso = '2026-08-05'; // local day after 2026-08-04

    expect(formatDayLabel(tomorrowDateIso, now)).toBe('Amanha');
  });

  it('does NOT label the bucket as Hoje for the UTC calendar date when it differs from the local date', () => {
    const now = new Date('2026-08-05T02:45:00.000Z'); // local day is still 2026-08-04
    const utcTodayDateIso = now.toISOString().slice(0, 10); // '2026-08-05', the buggy value

    expect(formatDayLabel(utcTodayDateIso, now)).not.toBe('Hoje');
  });
});

describe('getUpcomingRangeParams (from/to sent to dashboardApi.upcomingBuckets)', () => {
  it('uses the LOCAL calendar date as "from", not the UTC calendar date, near a negative-offset midnight boundary', () => {
    // Same straddling instant as above: local day 2026-08-04, UTC day 2026-08-05.
    const now = new Date('2026-08-05T02:45:00.000Z');

    const { from } = getUpcomingRangeParams(now);

    expect(from).toBe('2026-08-04');
    expect(from).not.toBe(now.toISOString().slice(0, 10));
  });

  it('the first bucket for "today" and the from/to params agree on the same calendar day (no off-by-one)', () => {
    const now = new Date('2026-08-05T02:45:00.000Z');

    const todayBucketDateIso = getLocalDateIso(now);
    const { from } = getUpcomingRangeParams(now);

    expect(from).toBe(todayBucketDateIso);
  });
});
