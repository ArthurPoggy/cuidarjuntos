import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { dashboardApi } from '../api/endpoints';
import type { CalendarData, CalendarEvent } from '../types/models';
import { getAdjacentMonth, getEventsForDate, getMonthParam } from '../utils/calendarNavigation';

function todayIso(): string {
  const now = new Date();
  const yyyy = now.getFullYear();
  const mm = String(now.getMonth() + 1).padStart(2, '0');
  const dd = String(now.getDate()).padStart(2, '0');
  return `${yyyy}-${mm}-${dd}`;
}

/**
 * Navegação de agenda por mês/dia (tarefa #110), consumindo
 * `dashboardApi.calendar()` (GET /api/v1/calendar/).
 *
 * Busca a grade do mês atual ao montar e sempre que `year`/`month` mudam
 * (via `goToNextMonth`/`goToPrevMonth`, que fazem o rollover de ano
 * corretamente). Expõe também a seleção de um dia (`selectDate`) e os
 * eventos exatos daquele dia (`selectedEvents`), sem vazar itens de dias
 * adjacentes.
 */
export function useCalendarNavigation() {
  const initial = useMemo(() => {
    const now = new Date();
    return { year: now.getFullYear(), month: now.getMonth() + 1 };
  }, []);

  const [year, setYear] = useState(initial.year);
  const [month, setMonth] = useState(initial.month);
  const [calendarData, setCalendarData] = useState<CalendarData | null>(null);
  const [loading, setLoading] = useState(true);
  const [selectedDate, setSelectedDate] = useState<string>(todayIso());

  const mounted = useRef(true);

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);

    dashboardApi
      .calendar({ m: getMonthParam(year, month) })
      .then(({ data }) => {
        if (!cancelled && mounted.current) {
          setCalendarData(data);
        }
      })
      .catch(() => {
        if (!cancelled && mounted.current) {
          setCalendarData(null);
        }
      })
      .finally(() => {
        if (!cancelled && mounted.current) {
          setLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [year, month]);

  const goToNextMonth = useCallback(() => {
    const next = getAdjacentMonth(year, month, 1);
    setYear(next.year);
    setMonth(next.month);
  }, [year, month]);

  const goToPrevMonth = useCallback(() => {
    const prev = getAdjacentMonth(year, month, -1);
    setYear(prev.year);
    setMonth(prev.month);
  }, [year, month]);

  const selectDate = useCallback((dateIso: string) => {
    setSelectedDate(dateIso);
  }, []);

  const selectedEvents: CalendarEvent[] = useMemo(
    () => getEventsForDate(calendarData, selectedDate),
    [calendarData, selectedDate]
  );

  return {
    year,
    month,
    calendarData,
    loading,
    goToNextMonth,
    goToPrevMonth,
    selectedDate,
    selectDate,
    selectedEvents,
  };
}
