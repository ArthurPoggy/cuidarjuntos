#!/usr/bin/env node
/**
 * Runner reprodutivel para os testes da tarefa #106 ("Unificar o componente
 * de card de registro usado no Dashboard e na lista de registros mobile").
 *
 * Nao ha jest/ts-jest configurado neste projeto (nem em package.json, nem
 * jest.config.js), entao os testes de #106 sao escritos como scripts Node
 * autocontidos (node:assert/strict + exit code). Este runner os torna
 * acessiveis via um unico comando padronizado:
 *
 *   npm run test:106
 *
 * Ele:
 *   1. Compila os arquivos de teste (e seus imports locais) com `tsc` para
 *      um diretorio temporario.
 *   2. Executa cada teste compilado com `node`.
 *   3. Sai com codigo 0 somente se todos os testes passarem; caso
 *      contrario, sai com codigo != 0 (propagando a falha para CI/terminal).
 */

const { execFileSync } = require('node:child_process');
const path = require('node:path');
const fs = require('node:fs');

const FRONTEND_ROOT = path.resolve(__dirname, '..');
const OUT_DIR = path.join(FRONTEND_ROOT, '.tmp-test-out-106');

const TEST_ENTRYPOINTS = [
  'src/utils/__tests__/formatters.test.ts',
  'src/components/__tests__/recordCardUnification.test.ts',
];

function run(cmd, args, opts = {}) {
  return execFileSync(cmd, args, {
    cwd: FRONTEND_ROOT,
    stdio: 'inherit',
    shell: process.platform === 'win32',
    ...opts,
  });
}

function main() {
  if (fs.existsSync(OUT_DIR)) {
    fs.rmSync(OUT_DIR, { recursive: true, force: true });
  }

  console.log('== Compilando testes da tarefa #106 (tsc) ==');
  try {
    run('npx', [
      'tsc',
      '--module',
      'commonjs',
      '--target',
      'es2019',
      '--esModuleInterop',
      '--skipLibCheck',
      '--outDir',
      OUT_DIR,
      ...TEST_ENTRYPOINTS,
    ]);
  } catch (err) {
    console.error('\nFalha ao compilar os testes da tarefa #106 (tsc).');
    process.exit(typeof err.status === 'number' ? err.status : 1);
  }

  let overallFailures = 0;

  for (const entry of TEST_ENTRYPOINTS) {
    const jsPath = path.join(
      OUT_DIR,
      entry.replace(/^src\//, '').replace(/\.ts$/, '.js'),
    );
    console.log(`\n== Executando ${entry} ==`);
    try {
      run('node', [jsPath]);
    } catch (err) {
      overallFailures += 1;
      console.error(`Falhou: ${entry}`);
    }
  }

  if (overallFailures > 0) {
    console.error(
      `\n${overallFailures}/${TEST_ENTRYPOINTS.length} arquivos de teste falharam.`,
    );
    process.exit(1);
  }

  console.log('\nTodos os testes da tarefa #106 passaram.');
  process.exit(0);
}

main();
