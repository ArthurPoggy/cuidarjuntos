import { renderHook, act, waitFor } from '@testing-library/react-native';
import type { CalendarData, CalendarEvent } from '../../types/models';

/**
 * Testes para o item da tarefa #110 "Consertar agenda -> MOBILE":
 * "Implementar navegacao de agenda por dia/semana/mes consumindo o endpoint
 * /calendar/ ja existente".
 *
 * Ver tambem frontend/src/utils/__tests__/calendarNavigation.test.ts, que
 * cobre a logica pura de calculo de mes/ano e selecao de dia extraida para
 * `frontend/src/utils/calendarNavigation.ts`.
 *
 * Este arquivo testa `frontend/src/hooks/useCalendarNavigation.ts`, um hook
 * ainda inexistente que a correcao deve criar, responsavel por:
 *
 *   - Chamar `dashboardApi.calendar({ m })` (frontend/src/api/endpoints.ts)
 *     ao montar e sempre que o mes ativo mudar, usando como `m` o primeiro
 *     dia (formato 'yyyy-MM-dd') do mes que deve ser exibido.
 *   - Expor `year`, `month`, `calendarData`, `loading` e as acoes
 *     `goToNextMonth()` / `goToPrevMonth()`, que avancam/retrocedem um mes
 *     (com rollover de ano correto) e disparam uma nova chamada a API com o
 *     `m` do novo mes alvo.
 *   - Expor `selectedDate` e `selectDate(dateIso)`, e `selectedEvents`
 *     (a lista de eventos do dia selecionado), que deve corresponder
 *     exatamente a `calendarData.events_by_date[selectedDate]` da resposta
 *     da API, sem vazar eventos de dias adjacentes.
 *
 * Ate esse hook ser criado, TODOS os testes abaixo falham por erro de
 * modulo nao encontrado ("Cannot find module '../useCalendarNavigation'")
 * -- essa e a falha esperada nesta etapa (somente testes, sem
 * implementacao da correcao).
 */

const mockCalendar = jest.fn();

jest.mock('../../api/endpoints', () => ({
  dashboardApi: {
    calendar: (...args: unknown[]) => mockCalendar(...args),
  },
}));

import { useCalendarNavigation } from '../useCalendarNavigation';

function buildCalendarEvent(title: string): CalendarEvent {
  return { type: 'medication', title, what: title, time: '08:00', who: 'Maria' };
}

function buildCalendarResponse(
  year: number,
  month: number,
  eventsByDate: Record<string, CalendarEvent[]>
): { data: CalendarData } {
  return {
    data: {
      year,
      month,
      month_name: 'Mes',
      weeks: [],
      days_with: Object.keys(eventsByDate).map((d) => Number(d.slice(-2))),
      today_iso: `${year}-${String(month).padStart(2, '0')}-01`,
      events_by_date: eventsByDate,
    },
  };
}

describe('hooks/useCalendarNavigation', () => {
  const ORIGINAL_TZ = process.env.TZ;

  beforeAll(() => {
    process.env.TZ = 'America/Sao_Paulo';
  });

  afterAll(() => {
    process.env.TZ = ORIGINAL_TZ;
  });

  beforeEach(() => {
    mockCalendar.mockReset();
    mockCalendar.mockResolvedValue(buildCalendarResponse(2026, 1, {}));
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  it('ao montar, chama dashboardApi.calendar com m = primeiro dia do mes atual', async () => {
    jest.useFakeTimers().setSystemTime(new Date('2026-01-15T12:00:00.000Z'));

    await renderHook(() => useCalendarNavigation());

    await waitFor(() => expect(mockCalendar).toHaveBeenCalledTimes(1));
    expect(mockCalendar).toHaveBeenCalledWith(
      expect.objectContaining({ m: '2026-01-01' })
    );
  });

  it('goToNextMonth a partir de dezembro incrementa o ano e chama a API com m do janeiro seguinte', async () => {
    jest.useFakeTimers().setSystemTime(new Date('2025-12-10T12:00:00.000Z'));
    mockCalendar.mockResolvedValue(buildCalendarResponse(2025, 12, {}));

    const { result } = await renderHook(() => useCalendarNavigation());

    await waitFor(() => expect(mockCalendar).toHaveBeenCalledTimes(1));

    await act(async () => {
      result.current.goToNextMonth();
    });

    await waitFor(() => expect(mockCalendar).toHaveBeenCalledTimes(2));

    expect(mockCalendar).toHaveBeenLastCalledWith(
      expect.objectContaining({ m: '2026-01-01' })
    );
    await waitFor(() => expect(result.current.year).toBe(2026));
    expect(result.current.month).toBe(1);
  });

  it('goToPrevMonth a partir de janeiro decrementa o ano e chama a API com m de dezembro anterior', async () => {
    jest.useFakeTimers().setSystemTime(new Date('2026-01-10T12:00:00.000Z'));
    mockCalendar.mockResolvedValue(buildCalendarResponse(2026, 1, {}));

    const { result } = await renderHook(() => useCalendarNavigation());

    await waitFor(() => expect(mockCalendar).toHaveBeenCalledTimes(1));

    await act(async () => {
      result.current.goToPrevMonth();
    });

    await waitFor(() => expect(mockCalendar).toHaveBeenCalledTimes(2));

    expect(mockCalendar).toHaveBeenLastCalledWith(
      expect.objectContaining({ m: '2025-12-01' })
    );
    await waitFor(() => expect(result.current.year).toBe(2025));
    expect(result.current.month).toBe(12);
  });

  it('selectDate expoe exatamente events_by_date[data] da resposta, sem itens de dias adjacentes', async () => {
    jest.useFakeTimers().setSystemTime(new Date('2026-01-15T12:00:00.000Z'));

    const eventsByDate: Record<string, CalendarEvent[]> = {
      '2026-01-14': [buildCalendarEvent('Evento dia 14')],
      '2026-01-15': [buildCalendarEvent('Evento dia 15 (A)'), buildCalendarEvent('Evento dia 15 (B)')],
      '2026-01-16': [buildCalendarEvent('Evento dia 16')],
    };
    mockCalendar.mockResolvedValue(buildCalendarResponse(2026, 1, eventsByDate));

    const { result } = await renderHook(() => useCalendarNavigation());

    await waitFor(() => expect(result.current.calendarData).not.toBeNull());

    await act(async () => {
      result.current.selectDate('2026-01-15');
    });

    expect(result.current.selectedDate).toBe('2026-01-15');
    expect(result.current.selectedEvents).toEqual(eventsByDate['2026-01-15']);
    expect(result.current.selectedEvents).toHaveLength(2);

    const titles = result.current.selectedEvents.map((e: CalendarEvent) => e.title);
    expect(titles).not.toEqual(expect.arrayContaining(['Evento dia 14']));
    expect(titles).not.toEqual(expect.arrayContaining(['Evento dia 16']));
  });

  it('selectDate para um dia sem eventos expoe selectedEvents vazio, sem vazar itens de outro dia', async () => {
    jest.useFakeTimers().setSystemTime(new Date('2026-01-15T12:00:00.000Z'));

    const eventsByDate: Record<string, CalendarEvent[]> = {
      '2026-01-16': [buildCalendarEvent('Evento dia 16')],
    };
    mockCalendar.mockResolvedValue(buildCalendarResponse(2026, 1, eventsByDate));

    const { result } = await renderHook(() => useCalendarNavigation());

    await waitFor(() => expect(result.current.calendarData).not.toBeNull());

    await act(async () => {
      result.current.selectDate('2026-01-20');
    });

    expect(result.current.selectedDate).toBe('2026-01-20');
    expect(result.current.selectedEvents).toEqual([]);
  });
});
