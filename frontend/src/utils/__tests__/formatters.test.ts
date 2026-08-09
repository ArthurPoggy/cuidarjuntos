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
import { formatRecordDateTime } from '../formatters';

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
