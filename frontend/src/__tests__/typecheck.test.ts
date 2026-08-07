import fs from 'fs';
import path from 'path';
import { execSync } from 'child_process';

/**
 * Gate para o item da tarefa #110 "Consertar agenda -> MOBILE": "Preparar
 * infraestrutura de testes automatizados no app mobile".
 *
 * O card exige explicitamente que exista uma forma automatizada de checar
 * tipos no app mobile (frontend/) e que ela passe com zero erros.
 *
 * Este teste verifica que:
 *  1. Existe um script `typecheck` em `frontend/package.json`.
 *  2. Esse script roda `tsc --noEmit` (respeitando o `tsconfig.json`, que
 *     tem `strict: true`).
 *  3. Rodar `npm run typecheck` dentro de `frontend/` termina com exit code
 *     0 e sem nenhuma linha de erro (`errorTS`/`error TS`) na saida do tsc.
 */

const FRONTEND_ROOT = path.resolve(__dirname, '..', '..');

function readPackageJson(): {
  scripts?: Record<string, string>;
} {
  const raw = fs.readFileSync(path.join(FRONTEND_ROOT, 'package.json'), 'utf-8');
  return JSON.parse(raw);
}

describe('Script typecheck do app mobile (frontend/)', () => {
  it('possui um script "typecheck" em package.json', () => {
    const pkg = readPackageJson();
    expect(pkg.scripts?.typecheck).toBeDefined();
  });

  it('o script "typecheck" invoca "tsc --noEmit"', () => {
    const pkg = readPackageJson();
    const script = pkg.scripts?.typecheck ?? '';
    expect(script).toEqual(expect.stringContaining('tsc'));
    expect(script).toEqual(expect.stringContaining('--noEmit'));
  });

  it('"npm run typecheck" termina com exit code 0 e sem erros TS na saida', () => {
    let output = '';
    let exitCode = 0;

    try {
      output = execSync('npm run typecheck', {
        cwd: FRONTEND_ROOT,
        encoding: 'utf-8',
        stdio: ['ignore', 'pipe', 'pipe'],
      });
    } catch (err) {
      const execErr = err as { status?: number; stdout?: string; stderr?: string };
      exitCode = execErr.status ?? 1;
      output = `${execErr.stdout ?? ''}${execErr.stderr ?? ''}`;
    }

    const hasTsErrorLine = /error TS\d+/.test(output);

    expect({ exitCode, hasTsErrorLine }).toEqual(
      expect.objectContaining({ exitCode: 0, hasTsErrorLine: false })
    );
  }, 120000);
});
