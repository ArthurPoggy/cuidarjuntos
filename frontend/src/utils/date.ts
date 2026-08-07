import { addDays, format, isSameDay, parse } from 'date-fns';

const WEEKDAYS = ['Domingo', 'Segunda', 'Terca', 'Quarta', 'Quinta', 'Sexta', 'Sabado'];

/**
 * Retorna a data LOCAL (nao UTC) de `date` no formato 'yyyy-MM-dd', usando o
 * fuso horario do sistema/relogio. Evita o bug de usar
 * `date.toISOString().slice(0, 10)`, que sempre retorna a data em UTC e pode
 * divergir da data local perto da meia-noite em fusos negativos (ex.:
 * America/Sao_Paulo, UTC-3).
 */
export function getLocalDateIso(date: Date = new Date()): string {
  return format(date, 'yyyy-MM-dd');
}

/**
 * Formata o rotulo de dia da agenda (UpcomingScreen) a partir de um
 * `dateIso` local (formato 'yyyy-MM-dd', como o que vem do backend),
 * comparando sempre datas locais entre si (nunca misturando data local com
 * data UTC).
 */
export function formatAgendaDayLabel(
  dateIso: string,
  referenceDate: Date = new Date()
): string {
  const d = parse(dateIso, 'yyyy-MM-dd', referenceDate);
  const tomorrow = addDays(referenceDate, 1);

  if (isSameDay(d, referenceDate)) return 'Hoje';
  if (isSameDay(d, tomorrow)) return 'Amanha';

  const dayOfWeek = WEEKDAYS[d.getDay()];
  return `${dayOfWeek}, ${format(d, 'dd/MM')}`;
}
