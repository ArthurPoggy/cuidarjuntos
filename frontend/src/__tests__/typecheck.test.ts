import { execSync } from 'child_process';
import path from 'path';

/**
 * Gate final do item da tarefa #105 "Checklist final de acessibilidade e
 * compatibilidade iOS/Android": `npx tsc --noEmit` no diretorio frontend deve
 * retornar zero erros de TypeScript para o projeto inteiro.
 *
 * Roda o compilador em modo --noEmit (nao gera artefatos) e falha o teste
 * mostrando a saida do tsc caso existam erros de tipo em qualquer arquivo do
 * projeto mobile.
 */

const FRONTEND_ROOT = path.resolve(__dirname, '..', '..');

describe('Typecheck do projeto mobile (gate final)', () => {
  it('npx tsc --noEmit nao reporta nenhum erro de TypeScript', () => {
    let output = '';
    let exitCode = 0;

    try {
      output = execSync('npx tsc --noEmit', {
        cwd: FRONTEND_ROOT,
        encoding: 'utf-8',
        stdio: ['ignore', 'pipe', 'pipe'],
      });
    } catch (err) {
      const execErr = err as { status?: number; stdout?: string; stderr?: string };
      exitCode = execErr.status ?? 1;
      output = `${execErr.stdout ?? ''}${execErr.stderr ?? ''}`;
    }

    expect({ exitCode, output }).toEqual({ exitCode: 0, output: '' });
  }, 120000);
});
