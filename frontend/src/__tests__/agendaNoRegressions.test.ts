/**
 * Regression guards for task #100, subtask "Checar ausência de regressões
 * nas telas que dependem da agenda e travar zero erros de TypeScript".
 *
 * These complement `typecheck.test.ts` (which locks down `npm run
 * typecheck` exiting 0) by locking down, at the source level, two
 * concrete consumers named in the subtask description:
 *
 *   1. `Header.tsx`'s '📅 Agenda' menu item still calls
 *      `navigation.navigate('Upcoming')`.
 *   2. `dashboardApi.upcomingBuckets` still resolves `{ buckets:
 *      UpcomingBucket[] }`, and `UpcomingBucket` / `BucketItem` in
 *      `src/types/models.ts` keep the exact public shape already consumed
 *      by `UpcomingScreen.tsx` (unchanged field names/types - the subtask
 *      explicitly forbids altering this public signature).
 *
 * These are source-level regression checks (regex/text matching) rather
 * than full component renders; the actual type-correctness of every
 * consumer is additionally enforced end-to-end by `npm run typecheck`
 * (typecheck.test.ts).
 */

import fs from 'fs';
import path from 'path';

const SRC_DIR = path.resolve(__dirname, '..');

describe('Header.tsx - Agenda navigation', () => {
  const headerSrc = fs.readFileSync(path.join(SRC_DIR, 'components', 'Header.tsx'), 'utf8');

  it('renders a "📅  Agenda" menu item', () => {
    expect(headerSrc).toMatch(/📅\s*Agenda/);
  });

  it("wires the Agenda menu item's onPress to navigation.navigate('Upcoming')", () => {
    // Isolate the Agenda menu item's own onPress block so this assertion
    // stays specific to that entry (and not to some other menu item that
    // happens to also navigate somewhere). The style prop is matched
    // loosely (`style=\{[^}]*styles\.menuItemText`) because it may be a
    // single object (`style={styles.menuItemText}`) or an array
    // (`style={[styles.menuItemText, activeRouteName === ... && ...]}`)
    // depending on whether active-item highlighting has been wired in.
    const agendaBlockMatch = headerSrc.match(
      /onPress=\{\(\)\s*=>\s*\{([\s\S]*?)\}\}\s*>\s*<Text\s+style=\{[^}]*styles\.menuItemText[^}]*\}[^>]*>\s*📅\s*Agenda/
    );

    expect(agendaBlockMatch).not.toBeNull();
    expect(agendaBlockMatch![1]).toMatch(/navigation\.navigate\(\s*['"]Upcoming['"]\s*\)/);
  });
});

describe('src/types/models.ts - UpcomingBucket / BucketItem public shape', () => {
  const modelsSrc = fs.readFileSync(path.join(SRC_DIR, 'types', 'models.ts'), 'utf8');

  function extractInterface(name: string): string {
    const match = modelsSrc.match(new RegExp(`interface ${name} \\{([\\s\\S]*?)\\}`));
    if (!match) throw new Error(`interface ${name} not found in models.ts`);
    return match[1];
  }

  it('UpcomingBucket keeps { date_iso: string; items: BucketItem[] }', () => {
    const body = extractInterface('UpcomingBucket');
    expect(body).toMatch(/date_iso:\s*string;/);
    expect(body).toMatch(/items:\s*BucketItem\[\];/);
  });

  it('BucketItem keeps its full field set with unchanged types', () => {
    const body = extractInterface('BucketItem');
    expect(body).toMatch(/id:\s*number;/);
    expect(body).toMatch(/type:\s*string;/);
    expect(body).toMatch(/title:\s*string;/);
    expect(body).toMatch(/time:\s*string;/);
    expect(body).toMatch(/who:\s*string;/);
    expect(body).toMatch(/status:\s*string;/);
    expect(body).toMatch(/series:\s*boolean;/);
  });
});

describe('dashboardApi.upcomingBuckets - response contract', () => {
  // client.ts pulls in expo-secure-store / axios interceptors that assume a
  // React Native runtime; mock it out so this suite can run under the
  // plain-Node jest environment used by this package (see jest.config.js).
  const getMock = jest.fn(() =>
    Promise.resolve({
      data: {
        ok: true,
        buckets: [{ date_iso: '2026-08-04', items: [] }],
        totals: {},
      },
    })
  );

  jest.doMock('../api/client', () => ({ __esModule: true, default: { get: getMock } }));

  afterEach(() => {
    getMock.mockClear();
  });

  it("calls GET '/upcoming/buckets/' with the given params and resolves { buckets: UpcomingBucket[] }", async () => {
    // Re-require after the mock above so `endpoints.ts` picks up the mocked
    // client instead of the real axios instance.
    const { dashboardApi } = require('../api/endpoints');

    const res = await dashboardApi.upcomingBuckets({ from: '2026-08-04', to: '2026-08-11' });

    expect(getMock).toHaveBeenCalledWith(
      '/upcoming/buckets/',
      { params: { from: '2026-08-04', to: '2026-08-11' } }
    );
    expect(Array.isArray(res.data.buckets)).toBe(true);
    expect(res.data.buckets[0]).toEqual(
      expect.objectContaining({ date_iso: expect.any(String), items: expect.any(Array) })
    );
  });
});
