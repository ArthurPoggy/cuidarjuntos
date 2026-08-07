/**
 * Regression tests for task #100, subtask "Checar ausência de regressões nas
 * telas que dependem da agenda e travar zero erros de TypeScript".
 *
 * Acceptance criteria under test:
 *   - `frontend/package.json` exposes a `typecheck` script running
 *     `tsc --noEmit`.
 *   - Running it (equivalent to `npm run typecheck` from inside `frontend/`)
 *     exits with code 0 - i.e. the whole project (including the agenda
 *     refactor from the previous subtasks) compiles clean with no
 *     TypeScript errors.
 *
 * The `typecheck` script does not exist yet on `package.json`, so both
 * `npm pkg get scripts.typecheck` (asserted directly against the parsed
 * file below) and `npm run typecheck` are expected to fail against the
 * current code - "Missing script: typecheck" - which is the intended red
 * state for this step: only tests are being added here.
 */

import { execFileSync } from 'child_process';
import path from 'path';
import fs from 'fs';

const FRONTEND_DIR = path.resolve(__dirname, '..', '..');

describe('frontend/package.json - "typecheck" script', () => {
  it('defines a "typecheck" script that runs `tsc --noEmit`', () => {
    const pkgRaw = fs.readFileSync(path.join(FRONTEND_DIR, 'package.json'), 'utf8');
    const pkg = JSON.parse(pkgRaw);

    expect(pkg.scripts).toBeDefined();
    expect(pkg.scripts.typecheck).toBe('tsc --noEmit');
  });
});

describe('`npm run typecheck` (frontend/)', () => {
  it('exits with code 0 and reports no TypeScript errors', () => {
    // Runs the script exactly the way the acceptance criteria describes:
    // `npx tsc --noEmit`, executable via `npm run typecheck` from inside
    // `frontend/`. `execFileSync` throws (non-zero exit code) if the script
    // is missing or if `tsc` reports any error, which is exactly what we
    // want to detect here.
    let stdout = '';
    let threw = false;
    try {
      stdout = execFileSync('npm', ['run', 'typecheck', '--silent'], {
        cwd: FRONTEND_DIR,
        encoding: 'utf8',
        shell: true,
      });
    } catch (err) {
      threw = true;
      const e = err as { stdout?: string; stderr?: string };
      // Surface the failure output to make a red run actionable.
      stdout = `${e.stdout ?? ''}\n${e.stderr ?? ''}`;
    }

    expect({ threw, output: stdout }).toEqual({ threw: false, output: expect.any(String) });
  }, 60_000);
});
