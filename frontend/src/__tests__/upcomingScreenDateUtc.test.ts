import fs from 'fs';
import path from 'path';

/**
 * Guarda de regressao para o item da tarefa #110 "Consertar agenda ->
 * MOBILE": "Corrigir bug de fuso horario nos rotulos e agrupamento de dias
 * da agenda (UpcomingScreen)".
 *
 * O bug: em frontend/src/screens/UpcomingScreen.tsx, `formatDayLabel`
 * calcula "hoje"/"amanha" comparando `today.toISOString().slice(0, 10)`
 * (data em UTC) com `dateIso` (data local vinda do backend). Isso classifica
 * itens no dia errado para usuarios em fusos negativos (ex.:
 * America/Sao_Paulo, UTC-3), especialmente perto da meia-noite local.
 *
 * A correcao exige extrair essa logica para uma funcao pura testavel em
 * frontend/src/utils/date.ts (ver frontend/src/utils/__tests__/date.test.ts)
 * e usa-la em UpcomingScreen.tsx no lugar do calculo inline baseado em UTC.
 *
 * Este teste verifica estaticamente o codigo-fonte de UpcomingScreen.tsx
 * para garantir que:
 *  1. Ele NAO contem mais o padrao `toISOString().slice(0, 10)` (ou
 *     equivalente) usado para calcular dia local a partir de `Date` -- esse
 *     padrao e sempre baseado em UTC e e a causa raiz do bug.
 *  2. Ele importa a formatacao de rotulo de dia a partir de
 *     `../utils/date` (o modulo pure/testavel extraido), em vez de
 *     reimplementar a logica inline.
 *
 * Contra o codigo atual (antes da correcao), a primeira asserção falha, pois
 * o padrao `toISOString().slice(0, 10)` ainda esta presente em
 * UpcomingScreen.tsx.
 */

const SCREEN_PATH = path.resolve(
  __dirname,
  '..',
  'screens',
  'UpcomingScreen.tsx'
);

function readScreenSource(): string {
  return fs.readFileSync(SCREEN_PATH, 'utf-8');
}

describe('UpcomingScreen nao deve calcular datas locais a partir de UTC', () => {
  it('nao usa mais toISOString().slice(0, 10) (ou equivalente) para obter o dia local', () => {
    const source = readScreenSource();

    const usesUtcSliceForLocalDate =
      /toISOString\(\)\s*\.\s*slice\(\s*0\s*,\s*10\s*\)/.test(source) ||
      /toISOString\(\)\s*\.\s*split\(\s*['"]T['"]\s*\)\s*\[\s*0\s*\]/.test(source);

    expect(usesUtcSliceForLocalDate).toBe(false);
  });

  it('importa a formatacao de rotulo de dia do modulo utils/date, em vez de reimplementa-la inline', () => {
    const source = readScreenSource();

    const importsFromDateUtils = /from\s+['"]\.\.\/utils\/date['"]/.test(source);

    expect(importsFromDateUtils).toBe(true);
  });
});
