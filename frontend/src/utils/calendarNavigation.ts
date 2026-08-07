import type { CalendarData, CalendarEvent } from '../types/models';

/**
 * Funções puras de cálculo de mês/ano e seleção de dia para a navegação de
 * agenda (tarefa #110), extraídas para fora de qualquer componente React
 * para ficarem testáveis isoladamente.
 */

/**
 * Dado um ano e um mês (1-12) de referência, devolve o mês seguinte
 * (direction = 1) ou anterior (direction = -1), fazendo o rollover de ano
 * corretamente (dezembro -> janeiro do ano seguinte; janeiro -> dezembro do
 * ano anterior).
 */
export function getAdjacentMonth(
  year: number,
  month: number,
  direction: 1 | -1
): { year: number; month: number } {
  let newYear = year;
  let newMonth = month + direction;

  if (newMonth > 12) {
    newMonth = 1;
    newYear += 1;
  } else if (newMonth < 1) {
    newMonth = 12;
    newYear -= 1;
  }

  return { year: newYear, month: newMonth };
}

/**
 * Devolve a data (primeiro dia do mês) no formato 'yyyy-MM-dd' que deve ser
 * enviada como parâmetro de query `m` para `dashboardApi.calendar()`, com
 * mês/dia sempre com 2 dígitos (zero à esquerda).
 */
export function getMonthParam(year: number, month: number): string {
  const mm = String(month).padStart(2, '0');
  return `${year}-${mm}-01`;
}

/**
 * Dado o `CalendarData` retornado pelo endpoint e uma data selecionada
 * (formato 'yyyy-MM-dd'), devolve exatamente
 * `calendarData.events_by_date[dateIso]` (ou `[]` se não houver entrada),
 * sem misturar eventos de dias adjacentes.
 */
export function getEventsForDate(
  calendarData: CalendarData | null,
  dateIso: string
): CalendarEvent[] {
  if (!calendarData) return [];
  return calendarData.events_by_date[dateIso] ?? [];
}
