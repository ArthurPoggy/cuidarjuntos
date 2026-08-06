/**
 * Teste para a tarefa #106 "Consertar incongruencias nos cards de registros
 * do dashboard -> MOBILE", item "Unificar o componente de card de registro
 * usado no Dashboard e na lista de registros (mobile)".
 *
 * Cobre a funcao de formatacao de data/hora unica e compartilhada
 * `formatRecordDateTime`, que deve viver em `frontend/src/utils/formatters.ts`
 * e ser reutilizada tanto por `RecordCard.tsx` quanto por
 * `RecordListScreen.tsx` (via reuso do proprio `RecordCard`), eliminando a
 * duplicacao/divergencia de formatacao entre:
 *   - RecordCard.tsx:      `{record.date} {record.time ? '• ' + record.time : ''}`
 *   - RecordListScreen.tsx: `{item.date} | {item.time ? item.time.slice(0, 5) : '--:--'}`
 *
 * Por nao haver, hoje, um runner Jest configurado neste projeto (nem
 * jest/ts-jest, nem jest.config.js, declarados em package.json), este
 * arquivo e escrito como um script Node autocontido: usa `node:assert/strict`
 * e encerra o processo com `process.exit(0)` quando todos os casos passam ou
 * `process.exit(1)` (com o motivo da falha impresso) caso contrario.
 *
 * Como rodar (a partir de frontend/), ou via `npm run test:106`:
 *   npx tsc --module commonjs --target es2019 --outDir .tmp-test-out \
 *     src/utils/formatters.ts src/utils/__tests__/formatters.test.ts
 *   node .tmp-test-out/utils/__tests__/formatters.test.js
 */

import assert from 'node:assert/strict';
// eslint-disable-next-line import/no-relative-parent-imports
import { formatRecordDateTime } from '../formatters';

type Case = {
  name: string;
  run: () => void;
};

const cases: Case[] = [
  {
    name: 'data com horario (HH:mm:ss) formata como dd/mm/yyyy com separador e HH:mm',
    run: () => {
      const result = formatRecordDateTime('2026-08-04', '14:30:00');
      assert.equal(result, '04/08/2026 • 14:30');
    },
  },
  {
    name: 'data com horario (HH:mm) formata como dd/mm/yyyy com separador e HH:mm',
    run: () => {
      const result = formatRecordDateTime('2026-01-05', '09:05');
      assert.equal(result, '05/01/2026 • 09:05');
    },
  },
  {
    name: 'data sem horario (time null) formata so a data, sem separador nem "--:--"',
    run: () => {
      const result = formatRecordDateTime('2026-08-04', null);
      assert.equal(result, '04/08/2026');
      assert.ok(!result.includes('--:--'));
      assert.ok(!result.includes('•'));
    },
  },
  {
    name: 'data sem horario (time undefined) formata so a data',
    run: () => {
      const result = formatRecordDateTime('2026-08-04');
      assert.equal(result, '04/08/2026');
    },
  },
  {
    name: 'data sem horario (time string vazia) formata so a data',
    run: () => {
      const result = formatRecordDateTime('2026-08-04', '');
      assert.equal(result, '04/08/2026');
    },
  },
  {
    name: 'date ausente (undefined) retorna fallback deterministico "-", nao lanca excecao',
    run: () => {
      const result = formatRecordDateTime(undefined, '14:30');
      assert.equal(result, '-');
    },
  },
  {
    name: 'date ausente (null) retorna fallback deterministico "-"',
    run: () => {
      const result = formatRecordDateTime(null, null);
      assert.equal(result, '-');
    },
  },
  {
    name: 'date ausente (string vazia) retorna fallback deterministico "-"',
    run: () => {
      const result = formatRecordDateTime('', '14:30');
      assert.equal(result, '-');
    },
  },
  {
    name: 'date invalido (nao ISO / nao parseavel) retorna fallback deterministico "-", nao lanca excecao',
    run: () => {
      const result = formatRecordDateTime('data-invalida', '14:30');
      assert.equal(result, '-');
    },
  },
  {
    name: 'a formatacao e deterministica: mesma entrada produz sempre a mesma saida, independente de quantas vezes/onde e chamada',
    run: () => {
      const a = formatRecordDateTime('2026-08-04', '14:30:00');
      const b = formatRecordDateTime('2026-08-04', '14:30:00');
      const c = formatRecordDateTime('2026-08-04', '14:30:00');
      assert.equal(a, b);
      assert.equal(b, c);
    },
  },
];

let failures = 0;

for (const testCase of cases) {
  try {
    testCase.run();
    // eslint-disable-next-line no-console
    console.log(`PASS - ${testCase.name}`);
  } catch (err) {
    failures += 1;
    // eslint-disable-next-line no-console
    console.error(`FAIL - ${testCase.name}`);
    // eslint-disable-next-line no-console
    console.error(err instanceof Error ? err.message : err);
  }
}

// eslint-disable-next-line no-console
console.log(`\n${cases.length - failures}/${cases.length} testes passaram.`);

if (failures > 0) {
  process.exit(1);
} else {
  process.exit(0);
}
