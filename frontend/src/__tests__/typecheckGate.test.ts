import fs from 'fs';
import path from 'path';
import packageJson from '../../package.json';

// Tarefa #99 (subtask 4): "gate final de zero erros TypeScript" precisa ser
// (a) reproduzível por um comando único, ex. `npm run typecheck` rodando
// `tsc --noEmit`, em vez de depender de alguém lembrar de rodar
// `npx tsc --noEmit` manualmente, e (b) documentado (ex. em um README do
// frontend), conforme pedido pelo critério de aceitação da subtask 4
// ("configurar/validar que `npx tsc --noEmit` roda como gate reproduzível
// (documentar comando único, ex. em README ou script npm `typecheck`)").
//
// Estes testes falham até que o script `typecheck` seja adicionado a
// frontend/package.json E documentado em um README do frontend — as duas
// metades do AC. Isso é intencional: nenhuma implementação foi feita nesta
// rodada, só os testes que expõem a lacuna.
describe('gate de TypeScript (frontend)', () => {
  it('define um script npm "typecheck" que roda tsc --noEmit', () => {
    const scripts = (packageJson as { scripts?: Record<string, string> }).scripts ?? {};

    expect(scripts).toHaveProperty('typecheck');
    expect(scripts.typecheck).toEqual(expect.stringContaining('tsc'));
    expect(scripts.typecheck).toEqual(expect.stringContaining('--noEmit'));
  });

  it('documenta o comando único de typecheck em um README do frontend', () => {
    const candidateReadmes = [
      path.resolve(__dirname, '..', '..', 'README.md'),
      path.resolve(__dirname, '..', '..', '..', 'README.md'),
    ];

    const existingReadmes = candidateReadmes.filter((file) => fs.existsSync(file));

    expect(existingReadmes.length).toBeGreaterThan(0);

    const documentsTypecheckCommand = existingReadmes.some((file) => {
      const content = fs.readFileSync(file, 'utf-8');
      return /npm run typecheck/.test(content) || /npx tsc --noEmit/.test(content);
    });

    expect(documentsTypecheckCommand).toBe(true);
  });
});
