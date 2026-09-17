/**
 * Agrupamento de registros/atividades em blocos do dia (tarefa #113).
 *
 * Faixas de horario adotadas:
 *  - Manha: 00:00 - 11:59
 *  - Tarde: 12:00 - 17:59
 *  - Noite: 18:00 - 23:59
 *
 * Registros sem horario definido (`time` vazio/nulo) caem no bloco "Manha",
 * pelo mesmo criterio usado no backend (`dashboard_data`, api/views/care.py)
 * ao ordenar registros sem horario como se fossem 00:00.
 */

export type PeriodKey = 'morning' | 'afternoon' | 'evening';

export const PERIOD_ORDER: PeriodKey[] = ['morning', 'afternoon', 'evening'];

export const PERIOD_LABELS: Record<PeriodKey, string> = {
  morning: 'Manhã',
  afternoon: 'Tarde',
  evening: 'Noite',
};

export function getPeriodForTime(time?: string | null): PeriodKey {
  if (!time) return 'morning';
  const hour = parseInt(time.slice(0, 2), 10);
  if (Number.isNaN(hour)) return 'morning';
  if (hour < 12) return 'morning';
  if (hour < 18) return 'afternoon';
  return 'evening';
}

export interface PeriodGroup<T> {
  period: PeriodKey;
  label: string;
  records: T[];
}

/**
 * Agrupa uma lista de registros (ja ordenada como o chamador desejar) em
 * blocos de manha/tarde/noite, preservando a ordem relativa dos registros
 * dentro de cada bloco. Blocos sem nenhum registro nao sao incluidos no
 * resultado.
 */
export function groupRecordsByPeriod<T extends { time?: string | null }>(
  records: T[]
): PeriodGroup<T>[] {
  const buckets: Record<PeriodKey, T[]> = {
    morning: [],
    afternoon: [],
    evening: [],
  };

  for (const record of records) {
    buckets[getPeriodForTime(record.time)].push(record);
  }

  return PERIOD_ORDER.filter((period) => buckets[period].length > 0).map(
    (period) => ({
      period,
      label: PERIOD_LABELS[period],
      records: buckets[period],
    })
  );
}

export interface DayPeriodGroup<T> {
  date: string;
  periods: PeriodGroup<T>[];
}

/**
 * Agrupa uma lista de registros primeiro por data e, dentro de cada data,
 * pelos blocos manha/tarde/noite (via `groupRecordsByPeriod`).
 *
 * A ordem das datas segue a ordem em que elas aparecem na lista de entrada
 * (a API retorna os registros ordenados por `-date`/`-time`), preservando a
 * navegacao cronologica dia a dia esperada ao filtrar um intervalo de datas
 * com o `PeriodFilter`. Sem isso, agrupar direto por bloco (ignorando a
 * data) misturaria registros de dias diferentes no mesmo bloco.
 */
export function groupRecordsByDayAndPeriod<
  T extends { time?: string | null; date: string }
>(records: T[]): DayPeriodGroup<T>[] {
  const dayOrder: string[] = [];
  const dayBuckets: Record<string, T[]> = {};

  for (const record of records) {
    const date = record.date;
    if (!dayBuckets[date]) {
      dayBuckets[date] = [];
      dayOrder.push(date);
    }
    dayBuckets[date].push(record);
  }

  return dayOrder.map((date) => ({
    date,
    periods: groupRecordsByPeriod(dayBuckets[date]),
  }));
}
