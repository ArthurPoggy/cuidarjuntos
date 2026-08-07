import type { CalendarData, CalendarEvent } from '../../types/models';

/**
 * Testes para o item da tarefa #110 "Consertar agenda -> MOBILE":
 * "Implementar navegacao de agenda por dia/semana/mes consumindo o endpoint
 * /calendar/ ja existente".
 *
 * O backend expoe GET /api/v1/calendar/ (api/views/care.py:calendar_data),
 * que recebe um parametro de query `m` (uma data qualquer dentro do mes
 * alvo -- o backend faz `month_ref.replace(day=1)`) e devolve uma grade de
 * semanas do mes (`weeks`), os dias com evento (`days_with`) e um mapa
 * `events_by_date` (chave = data ISO 'yyyy-MM-dd') com os eventos daquele
 * dia. O frontend ja tem `dashboardApi.calendar()` (frontend/src/api/endpoints.ts)
 * e os tipos `CalendarData`/`CalendarEvent` (frontend/src/types/models.ts),
 * mas nenhuma tela consome isso hoje -- a unica tela de agenda
 * (UpcomingScreen) e uma lista plana, sem navegacao por mes/dia.
 *
 * Este arquivo testa `frontend/src/utils/calendarNavigation.ts`, um modulo
 * ainda inexistente que a correcao deve criar, extraindo a logica pura de
 * calculo de mes/ano e de selecao de dia para fora de qualquer componente
 * React, para ficar testavel isoladamente:
 *
 *   - `getAdjacentMonth(year: number, month: number, direction: 1 | -1): { year: number; month: number }`
 *     -- dado um ano e um mes (1-12) de referencia, devolve o mes seguinte
 *     (direction = 1) ou anterior (direction = -1), fazendo o rollover de
 *     ano corretamente (dezembro -> janeiro do ano seguinte; janeiro ->
 *     dezembro do ano anterior).
 *   - `getMonthParam(year: number, month: number): string` -- devolve a
 *     data (primeiro dia do mes) no formato 'yyyy-MM-dd' que deve ser
 *     enviada como parametro de query `m` para `dashboardApi.calendar()`,
 *     com mes/dia sempre com 2 digitos (zero a esquerda).
 *   - `getEventsForDate(calendarData: CalendarData | null, dateIso: string): CalendarEvent[]`
 *     -- dado o `CalendarData` retornado pelo endpoint e uma data
 *     selecionada (formato 'yyyy-MM-dd'), devolve exatamente
 *     `calendarData.events_by_date[dateIso]` (ou `[]` se nao houver
 *     entrada), sem misturar eventos de dias adjacentes.
 *
 * Ate esse modulo ser criado, TODOS os testes abaixo falham por erro de
 * modulo nao encontrado ("Cannot find module '../calendarNavigation'") --
 * essa e a falha esperada nesta etapa (somente testes, sem implementacao da
 * correcao).
 */
import {
  getAdjacentMonth,
  getMonthParam,
  getEventsForDate,
} from '../calendarNavigation';

function buildCalendarEvent(title: string): CalendarEvent {
  return { type: 'medication', title, what: title, time: '08:00', who: 'Maria' };
}

function buildCalendarData(
  overrides: Partial<CalendarData> = {}
): CalendarData {
  return {
    year: 2026,
    month: 1,
    month_name: 'Janeiro',
    weeks: [],
    days_with: [14, 15, 16],
    today_iso: '2026-01-15',
    events_by_date: {
      '2026-01-14': [buildCalendarEvent('Evento dia 14 (A)'), buildCalendarEvent('Evento dia 14 (B)')],
      '2026-01-15': [buildCalendarEvent('Evento dia 15')],
      '2026-01-16': [
        buildCalendarEvent('Evento dia 16 (A)'),
        buildCalendarEvent('Evento dia 16 (B)'),
        buildCalendarEvent('Evento dia 16 (C)'),
      ],
    },
    ...overrides,
  };
}

describe('utils/calendarNavigation - getAdjacentMonth', () => {
  it('avancar um mes a partir de dezembro incrementa o ano (rollover dez/ano N -> jan/ano N+1)', () => {
    expect(getAdjacentMonth(2025, 12, 1)).toEqual({ year: 2026, month: 1 });
  });

  it('retroceder um mes a partir de janeiro decrementa o ano (rollover jan/ano N -> dez/ano N-1)', () => {
    expect(getAdjacentMonth(2026, 1, -1)).toEqual({ year: 2025, month: 12 });
  });

  it('avancar dentro do mesmo ano nao altera o ano', () => {
    expect(getAdjacentMonth(2026, 5, 1)).toEqual({ year: 2026, month: 6 });
  });

  it('retroceder dentro do mesmo ano nao altera o ano', () => {
    expect(getAdjacentMonth(2026, 5, -1)).toEqual({ year: 2026, month: 4 });
  });

  it('encadear avancos em dezembro repetidas vezes continua incrementando o ano corretamente', () => {
    let ref = { year: 2025, month: 11 };
    ref = getAdjacentMonth(ref.year, ref.month, 1); // dez/2025
    ref = getAdjacentMonth(ref.year, ref.month, 1); // jan/2026
    expect(ref).toEqual({ year: 2026, month: 1 });
  });
});

describe('utils/calendarNavigation - getMonthParam', () => {
  it('retorna o primeiro dia do mes no formato yyyy-MM-dd, com mes de 2 digitos', () => {
    expect(getMonthParam(2026, 1)).toBe('2026-01-01');
  });

  it('retorna o primeiro dia do mes para dezembro (mes = 12)', () => {
    expect(getMonthParam(2026, 12)).toBe('2026-12-01');
  });

  it('o parametro `m` do mes alvo apos rollover dez -> jan corresponde ao primeiro dia de janeiro do ano seguinte', () => {
    const next = getAdjacentMonth(2025, 12, 1);
    expect(getMonthParam(next.year, next.month)).toBe('2026-01-01');
  });

  it('o parametro `m` do mes alvo apos rollover jan -> dez corresponde ao primeiro dia de dezembro do ano anterior', () => {
    const prev = getAdjacentMonth(2026, 1, -1);
    expect(getMonthParam(prev.year, prev.month)).toBe('2025-12-01');
  });
});

describe('utils/calendarNavigation - getEventsForDate', () => {
  it('retorna exatamente os itens de events_by_date[dataSelecionada], sem vazar itens de dias adjacentes', () => {
    const data = buildCalendarData();

    const eventsDay15 = getEventsForDate(data, '2026-01-15');

    expect(eventsDay15).toEqual(data.events_by_date['2026-01-15']);
    expect(eventsDay15).toHaveLength(1);
    expect(eventsDay15.map((e) => e.title)).not.toEqual(
      expect.arrayContaining(['Evento dia 14 (A)', 'Evento dia 14 (B)'])
    );
    expect(eventsDay15.map((e) => e.title)).not.toEqual(
      expect.arrayContaining(['Evento dia 16 (A)', 'Evento dia 16 (B)', 'Evento dia 16 (C)'])
    );
  });

  it('retorna todos (e somente) os itens de um dia com multiplos eventos', () => {
    const data = buildCalendarData();

    const eventsDay16 = getEventsForDate(data, '2026-01-16');

    expect(eventsDay16).toEqual(data.events_by_date['2026-01-16']);
    expect(eventsDay16).toHaveLength(3);
  });

  it('retorna array vazio para um dia sem eventos, em vez de undefined', () => {
    const data = buildCalendarData();

    expect(getEventsForDate(data, '2026-01-20')).toEqual([]);
  });

  it('retorna array vazio quando calendarData ainda nao foi carregado (null)', () => {
    expect(getEventsForDate(null, '2026-01-15')).toEqual([]);
  });
});
