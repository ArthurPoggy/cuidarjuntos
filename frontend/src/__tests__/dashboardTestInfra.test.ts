import fs from 'fs';
import path from 'path';
import { execSync } from 'child_process';

/**
 * Gate para o item da tarefa #109 "Deixar o dashboard em grid padrao ->
 * MOBILE": "Criar infraestrutura minima de testes automatizados no
 * frontend RN".
 *
 * A infraestrutura generica de testes (jest-expo, @testing-library/react-native,
 * preset "jest-expo" em jest.config.js) ja e coberta pelos gates das tarefas
 * #105 (src/__tests__/testAutomationInfra.test.ts) e #107
 * (src/__tests__/typecheck.test.ts). Este arquivo cobre apenas o que e
 * especifico da #109: o script `test` em si e o smoke test do dashboard
 * (DashboardScreen.smoke.test.tsx).
 *
 * IMPORTANTE sobre recursao: este arquivo e descoberto e executado pelo
 * proprio `npm test`/`npx jest` da suite completa. Por isso, ao contrario de
 * uma rodada anterior reprovada em review, ESTE arquivo nunca invoca
 * `npm test` (sem escopo) de dentro de um teste — isso causaria uma cadeia
 * infinita de processos filhos rodando a suite inteira de novo (o filho
 * re-executaria este mesmo teste, que dispararia um neto, e assim por
 * diante, ate estourar timeout/recursos). Seguindo a convencao ja usada em
 * src/__tests__/testAutomationInfra.test.ts para o smoke test da #105, o
 * smoke test do dashboard e executado de forma isolada via
 * `npx jest --testPathPattern=... --silent`, escopando a um unico arquivo.
 *
 * Este teste verifica que:
 *  1. Existe um script `"test"` (que invoca jest) em `frontend/package.json`.
 *  2. `npm test -- --listTests`, executado dentro de `frontend/`, termina
 *     com exit code 0 (sem erro de configuracao) e lista o smoke test do
 *     dashboard (`DashboardScreen.smoke.test.tsx`).
 *  3. O smoke test do dashboard, executado isoladamente via
 *     `npx jest --testPathPattern=DashboardScreen.smoke --silent`, termina
 *     com exit code 0.
 */

const FRONTEND_ROOT = path.resolve(__dirname, '..', '..');

function readPackageJson(): {
  scripts?: Record<string, string>;
} {
  const raw = fs.readFileSync(path.join(FRONTEND_ROOT, 'package.json'), 'utf-8');
  return JSON.parse(raw);
}

function runCommand(cmd: string): { exitCode: number; output: string } {
  try {
    const output = execSync(cmd, {
      cwd: FRONTEND_ROOT,
      encoding: 'utf-8',
      stdio: ['ignore', 'pipe', 'pipe'],
    });
    return { exitCode: 0, output };
  } catch (err) {
    const execErr = err as { status?: number; stdout?: string; stderr?: string };
    return {
      exitCode: execErr.status ?? 1,
      output: `${execErr.stdout ?? ''}${execErr.stderr ?? ''}`,
    };
  }
}

describe('Infraestrutura minima de testes automatizados do dashboard (frontend/)', () => {
  it('possui um script "test" que invoca jest em package.json', () => {
    const pkg = readPackageJson();
    expect(pkg.scripts?.test).toEqual(expect.stringContaining('jest'));
  });

  it('"npm test -- --listTests" roda sem erro de configuracao e lista o smoke test do dashboard', () => {
    const { exitCode, output } = runCommand('npm test -- --listTests');

    expect(exitCode).toBe(0);
    expect(output).toEqual(expect.stringContaining('DashboardScreen.smoke.test'));
  }, 120000);

  it('o smoke test do dashboard passa quando executado isoladamente (npx jest exit code 0)', () => {
    const { exitCode } = runCommand(
      'npx jest --testPathPattern=DashboardScreen.smoke --silent'
    );

    expect(exitCode).toBe(0);
  }, 120000);
});
