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
 */

import assert from 'node:assert/strict';
import { formatRecordDateTime, formatRelativeTime } from '../formatters';

describe('formatRecordDateTime', () => {
  it('data com horario (HH:mm:ss) formata como dd/mm/yyyy com separador e HH:mm', () => {
    const result = formatRecordDateTime('2026-08-04', '14:30:00');
    assert.equal(result, '04/08/2026 • 14:30');
  });

  it('data com horario (HH:mm) formata como dd/mm/yyyy com separador e HH:mm', () => {
    const result = formatRecordDateTime('2026-01-05', '09:05');
    assert.equal(result, '05/01/2026 • 09:05');
  });

  it('data sem horario (time null) formata so a data, sem separador nem "--:--"', () => {
    const result = formatRecordDateTime('2026-08-04', null);
    assert.equal(result, '04/08/2026');
    assert.ok(!result.includes('--:--'));
    assert.ok(!result.includes('•'));
  });

  it('data sem horario (time undefined) formata so a data', () => {
    const result = formatRecordDateTime('2026-08-04');
    assert.equal(result, '04/08/2026');
  });

  it('data sem horario (time string vazia) formata so a data', () => {
    const result = formatRecordDateTime('2026-08-04', '');
    assert.equal(result, '04/08/2026');
  });

  it('date ausente (undefined) retorna fallback deterministico "-", nao lanca excecao', () => {
    const result = formatRecordDateTime(undefined, '14:30');
    assert.equal(result, '-');
  });

  it('date ausente (null) retorna fallback deterministico "-"', () => {
    const result = formatRecordDateTime(null, null);
    assert.equal(result, '-');
  });

  it('date ausente (string vazia) retorna fallback deterministico "-"', () => {
    const result = formatRecordDateTime('', '14:30');
    assert.equal(result, '-');
  });

  it('date invalido (nao ISO / nao parseavel) retorna fallback deterministico "-", nao lanca excecao', () => {
    const result = formatRecordDateTime('data-invalida', '14:30');
    assert.equal(result, '-');
  });

  it('a formatacao e deterministica: mesma entrada produz sempre a mesma saida, independente de quantas vezes/onde e chamada', () => {
    const a = formatRecordDateTime('2026-08-04', '14:30:00');
    const b = formatRecordDateTime('2026-08-04', '14:30:00');
    const c = formatRecordDateTime('2026-08-04', '14:30:00');
    assert.equal(a, b);
    assert.equal(b, c);
  });
});

/**
 * Teste para a tarefa #127 "Timing do registro (colocado ha X horas)".
 *
 * Cobre a funcao `formatRelativeTime`, que deve viver em
 * `frontend/src/utils/formatters.ts` e produzir um texto relativo
 * ("ha X minutos/horas/dias") a partir da data/hora de um CareRecord,
 * recebendo opcionalmente um instante de referencia (`now`) para tornar o
 * resultado deterministico em testes.
 */
describe('formatRelativeTime', () => {
  const NOW = new Date(2026, 7, 4, 15, 0, 0); // 04/08/2026 15:00:00 local

  it('registro ha menos de 1 minuto retorna "agora mesmo"', () => {
    const result = formatRelativeTime('2026-08-04', '14:59:30', NOW);
    assert.equal(result, 'agora mesmo');
  });

  it('registro ha 1 minuto usa singular', () => {
    const result = formatRelativeTime('2026-08-04', '14:59:00', NOW);
    assert.equal(result, 'ha 1 minuto');
  });

  it('registro ha 30 minutos usa plural', () => {
    const result = formatRelativeTime('2026-08-04', '14:30:00', NOW);
    assert.equal(result, 'ha 30 minutos');
  });

  it('registro ha 1 hora usa singular', () => {
    const result = formatRelativeTime('2026-08-04', '14:00:00', NOW);
    assert.equal(result, 'ha 1 hora');
  });

  it('registro ha 3 horas usa plural', () => {
    const result = formatRelativeTime('2026-08-04', '12:00:00', NOW);
    assert.equal(result, 'ha 3 horas');
  });

  it('registro ha 1 dia usa singular', () => {
    const result = formatRelativeTime('2026-08-03', '15:00:00', NOW);
    assert.equal(result, 'ha 1 dia');
  });

  it('registro ha 2 dias usa plural', () => {
    const result = formatRelativeTime('2026-08-02', '15:00:00', NOW);
    assert.equal(result, 'ha 2 dias');
  });

  it('registro ha mais de 6 dias volta para a data absoluta dd/mm/yyyy', () => {
    const result = formatRelativeTime('2026-07-20', '15:00:00', NOW);
    assert.equal(result, formatRecordDateTime('2026-07-20', '15:00:00'));
  });

  it('registro sem horario usa meia-noite como referencia (dias inteiros)', () => {
    const result = formatRelativeTime('2026-08-04', null, NOW);
    assert.equal(result, 'ha 15 horas');
  });

  it('registro no futuro proximo retorna "agora mesmo"', () => {
    const result = formatRelativeTime('2026-08-04', '15:00:20', NOW);
    assert.equal(result, 'agora mesmo');
  });

  it('registro no futuro distante usa "em X minutos/horas/dias"', () => {
    const result = formatRelativeTime('2026-08-04', '16:00:00', NOW);
    assert.equal(result, 'em 1 hora');
  });

  it('date ausente/invalida retorna o fallback deterministico "-"', () => {
    assert.equal(formatRelativeTime(undefined, '14:30', NOW), '-');
    assert.equal(formatRelativeTime('data-invalida', '14:30', NOW), '-');
  });
});
