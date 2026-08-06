/**
 * Teste para a tarefa #106 "Consertar incongruencias nos cards de registros
 * do dashboard -> MOBILE", item "Unificar o componente de card de registro
 * usado no Dashboard e na lista de registros (mobile)".
 *
 * O teste em `src/utils/__tests__/formatters.test.ts` cobre apenas a funcao
 * pura `formatRecordDateTime` chamada isoladamente — ele NAO comprova que
 * `RecordCard.tsx` (usado por DashboardScreen) e `RecordListScreen.tsx`
 * passaram a compartilhar o mesmo componente/formatacao de card, que e o
 * cerne do criterio de aceitacao ("unificar o componente de card").
 *
 * Este arquivo faz uma verificacao estatica (leitura de codigo-fonte, sem
 * precisar montar componentes React Native) dos dois arquivos envolvidos e
 * falha caso:
 *
 *  1. `RecordListScreen.tsx` continue definindo seu proprio renderer de card
 *     divergente (`renderRecordCard`/JSX de card duplicado) em vez de
 *     reutilizar o componente `RecordCard`.
 *  2. `RecordListScreen.tsx` nao importe/use o componente compartilhado
 *     `RecordCard` de `../components/RecordCard`.
 *  3. `RecordCard.tsx` nao importe/use a funcao de formatacao compartilhada
 *     `formatRecordDateTime` de `../utils/formatters` (ou seja, continue
 *     formatando `record.date`/`record.time` "na mao", divergente do que
 *     `RecordListScreen` faz).
 *  4. O padrao antigo e divergente de formatacao de data ainda aparecer em
 *     `RecordListScreen.tsx` (`item.time.slice(0, 5)` / `'--:--'`), sinal de
 *     que a duplicacao nao foi removida.
 *
 * Por nao haver jest/testing-library configurados neste projeto hoje, e
 * escrito como script Node autocontido (`node:assert/strict` + exit code),
 * na mesma convencao de `formatters.test.ts`. Nao depende de tipos/typings
 * de react-native: le os arquivos-fonte como texto puro via `fs`.
 *
 * Como rodar (a partir de frontend/), ou via `npm run test:106`:
 *   npx tsc --module commonjs --target es2019 --outDir .tmp-test-out \
 *     src/components/__tests__/recordCardUnification.test.ts
 *   node .tmp-test-out/components/__tests__/recordCardUnification.test.js
 */

import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';

// Resolvido a partir do diretorio de trabalho (frontend/), e nao de
// `__dirname`: apos a compilacao com `tsc` para um `outDir` temporario,
// `__dirname` aponta para dentro desse diretorio de saida (que nao contem
// os arquivos .tsx fonte), entao a resolucao precisa ser feita a partir da
// raiz do projeto frontend/ (onde este script sempre e executado, ver
// scripts/test-106.js e o `npm run test:106`).
const FRONTEND_ROOT = process.cwd();
const RECORD_CARD_PATH = path.resolve(
  FRONTEND_ROOT,
  'src',
  'components',
  'RecordCard.tsx',
);
const RECORD_LIST_SCREEN_PATH = path.resolve(
  FRONTEND_ROOT,
  'src',
  'screens',
  'RecordListScreen.tsx',
);

type Case = {
  name: string;
  run: () => void;
};

const readSource = (filePath: string): string => {
  assert.ok(
    fs.existsSync(filePath),
    `Arquivo esperado nao encontrado: ${filePath}`,
  );
  return fs.readFileSync(filePath, 'utf-8');
};

const cases: Case[] = [
  {
    name: 'RecordListScreen.tsx importa o componente compartilhado RecordCard',
    run: () => {
      const source = readSource(RECORD_LIST_SCREEN_PATH);
      const importsRecordCard =
        /import\s+RecordCard\s+from\s+['"]\.\.\/components\/RecordCard['"]/.test(
          source,
        );
      assert.ok(
        importsRecordCard,
        'RecordListScreen.tsx deveria importar `RecordCard` de ' +
          '"../components/RecordCard" para reutilizar o mesmo card do ' +
          'Dashboard, mas nao importa.',
      );
    },
  },
  {
    name: 'RecordListScreen.tsx usa <RecordCard /> na renderizacao da lista (nao um renderer de card proprio)',
    run: () => {
      const source = readSource(RECORD_LIST_SCREEN_PATH);
      const usesRecordCardJsx = /<RecordCard\b/.test(source);
      assert.ok(
        usesRecordCardJsx,
        'RecordListScreen.tsx deveria renderizar <RecordCard .../> para ' +
          'cada item da lista, reaproveitando o mesmo componente usado no ' +
          'Dashboard, mas nao encontrei uso de <RecordCard.',
      );
    },
  },
  {
    name: 'RecordListScreen.tsx nao define mais um renderer de card divergente proprio (renderRecordCard local)',
    run: () => {
      const source = readSource(RECORD_LIST_SCREEN_PATH);
      const definesOwnRenderer = /const\s+renderRecordCard\s*=/.test(source);
      assert.ok(
        !definesOwnRenderer,
        'RecordListScreen.tsx ainda define sua propria funcao ' +
          '`renderRecordCard`, duplicando (e divergindo de) o card usado ' +
          'no Dashboard, em vez de reutilizar `RecordCard`.',
      );
    },
  },
  {
    name: 'RecordListScreen.tsx nao contem mais o padrao antigo e divergente de formatacao de data/hora',
    run: () => {
      const source = readSource(RECORD_LIST_SCREEN_PATH);
      const hasOldDivergentFormatting =
        source.includes('.slice(0, 5)') || source.includes("'--:--'");
      assert.ok(
        !hasOldDivergentFormatting,
        'RecordListScreen.tsx ainda contem a formatacao de data/hora ' +
          'antiga e divergente (`item.time.slice(0, 5)` / `\'--:--\'`), ' +
          'que deveria ter sido substituida pela formatacao compartilhada.',
      );
    },
  },
  {
    name: 'RecordCard.tsx usa a funcao de formatacao compartilhada formatRecordDateTime',
    run: () => {
      const source = readSource(RECORD_CARD_PATH);
      const importsFormatter =
        /import\s+\{[^}]*\bformatRecordDateTime\b[^}]*\}\s+from\s+['"]\.\.\/utils\/formatters['"]/.test(
          source,
        );
      assert.ok(
        importsFormatter,
        'RecordCard.tsx deveria importar `formatRecordDateTime` de ' +
          '"../utils/formatters" e usa-la para formatar `record.date`/' +
          '`record.time`, em vez de concatenar os campos crus na marcacao, ' +
          'mas o import nao foi encontrado.',
      );
      const usesFormatterCall = /formatRecordDateTime\s*\(/.test(source);
      assert.ok(
        usesFormatterCall,
        'RecordCard.tsx importa `formatRecordDateTime` mas nao chega a ' +
          'chama-la na renderizacao do card.',
      );
    },
  },
  {
    name: 'RecordListScreen.tsx tambem depende, direta ou indiretamente (via RecordCard), de formatRecordDateTime',
    run: () => {
      const source = readSource(RECORD_LIST_SCREEN_PATH);
      const usesRecordCardJsx = /<RecordCard\b/.test(source);
      const importsFormatterDirectly =
        /formatRecordDateTime/.test(source);
      assert.ok(
        usesRecordCardJsx || importsFormatterDirectly,
        'RecordListScreen.tsx precisa usar a mesma formatacao de data/hora ' +
          'que o Dashboard, seja reutilizando <RecordCard /> (que ja usa ' +
          'formatRecordDateTime), seja importando formatRecordDateTime ' +
          'diretamente. Nenhuma das duas coisas foi encontrada.',
      );
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
