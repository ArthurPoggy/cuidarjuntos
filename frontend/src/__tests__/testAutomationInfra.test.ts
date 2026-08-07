import fs from 'fs';
import path from 'path';
import { execSync } from 'child_process';

/**
 * Gate para o item da tarefa #110 "Consertar agenda -> MOBILE": "Preparar
 * infraestrutura de testes automatizados no app mobile".
 *
 * Hoje `frontend/` nao tem NENHUMA suite de testes configurada: nao existe
 * `jest.config.js`, nao existe script `test` em package.json, e as libs de
 * teste (jest, jest-expo, @testing-library/react-native) nao estao
 * declaradas como devDependencies (mesmo que alguma tenha sido instalada
 * manualmente em node_modules, package.json/package-lock.json nao refletem
 * isso). Isso impede validar automaticamente qualquer correcao feita na
 * agenda.
 *
 * Este teste verifica que:
 *  1. `jest-expo` e `@testing-library/react-native` estao declarados como
 *     devDependencies do app mobile em package.json.
 *  2. `package.json` tem um script `test` executando jest.
 *  3. `jest.config.js` existe, usa o preset "jest-expo" (necessario para
 *     poder renderizar componentes React Native/Expo em ambiente de teste)
 *     e o `testMatch`/`testRegex` cobre arquivos `.test.tsx` (nao so
 *     `.test.ts`).
 *  4. Existe um teste de smoke que renderiza um componente React Native via
 *     `@testing-library/react-native` (src/__tests__/smoke.test.tsx) e que
 *     `npm test` roda com sucesso (exit code 0, pelo menos 1 teste
 *     passando) quando executado na raiz de `frontend/`.
 */

const FRONTEND_ROOT = path.resolve(__dirname, '..', '..');

function readPackageJson(): {
  devDependencies?: Record<string, string>;
  dependencies?: Record<string, string>;
  scripts?: Record<string, string>;
} {
  const raw = fs.readFileSync(path.join(FRONTEND_ROOT, 'package.json'), 'utf-8');
  return JSON.parse(raw);
}

describe('Infraestrutura de testes automatizados do app mobile (frontend/)', () => {
  it('possui jest como devDependency', () => {
    const pkg = readPackageJson();
    expect(pkg.devDependencies?.jest).toBeDefined();
  });

  it('possui jest-expo como devDependency', () => {
    const pkg = readPackageJson();
    expect(pkg.devDependencies?.['jest-expo']).toBeDefined();
  });

  it('possui @testing-library/react-native como devDependency', () => {
    const pkg = readPackageJson();
    expect(pkg.devDependencies?.['@testing-library/react-native']).toBeDefined();
  });

  it('possui um script "test" em package.json', () => {
    const pkg = readPackageJson();
    expect(pkg.scripts?.test).toBeDefined();
  });

  it('jest.config.js existe e usa o preset jest-expo (direto ou em um projeto de multi-projeto)', () => {
    // eslint-disable-next-line @typescript-eslint/no-var-requires
    const config = require(path.join(FRONTEND_ROOT, 'jest.config.js'));
    const configs = Array.isArray(config.projects) ? config.projects : [config];
    const usesJestExpo = configs.some((c: { preset?: string }) => c.preset === 'jest-expo');
    expect(usesJestExpo).toBe(true);
  });

  it('jest.config.js reconhece arquivos de teste de componente (.test.tsx), direto ou em um projeto de multi-projeto', () => {
    // eslint-disable-next-line @typescript-eslint/no-var-requires
    const config = require(path.join(FRONTEND_ROOT, 'jest.config.js'));
    const configs = Array.isArray(config.projects) ? config.projects : [config];
    const coversTsx = configs.some((c: { testMatch?: string[]; testRegex?: string[] }) => {
      const testMatch = c.testMatch ?? c.testRegex ?? [];
      const patterns = Array.isArray(testMatch) ? testMatch : [testMatch];
      return patterns.some((pattern) => String(pattern).includes('tsx'));
    });
    expect(coversTsx).toBe(true);
  });

  it('"npm test" roda com sucesso: exit code 0 e pelo menos 1 teste passando', () => {
    let output = '';
    let exitCode = 0;

    try {
      output = execSync('npm test -- --testPathPattern=smoke 2>&1', {
        cwd: FRONTEND_ROOT,
        encoding: 'utf-8',
        stdio: ['ignore', 'pipe', 'pipe'],
      });
    } catch (err) {
      const execErr = err as { status?: number; stdout?: string; stderr?: string };
      exitCode = execErr.status ?? 1;
      output = `${execErr.stdout ?? ''}${execErr.stderr ?? ''}`;
    }

    const passedAtLeastOne = /Tests:\s+\d+ passed/.test(output);

    expect({ exitCode, passedAtLeastOne }).toEqual(
      expect.objectContaining({ exitCode: 0, passedAtLeastOne: true })
    );
  }, 120000);
});
