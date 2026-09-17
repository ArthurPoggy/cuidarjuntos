/**
 * Utilitarios de formatacao compartilhados entre telas/componentes que
 * exibem registros de cuidado (CareRecord), evitando divergencias de
 * formatacao de data/hora entre o Dashboard e a lista de registros.
 */

const FALLBACK = '-';

/**
 * Formata a data/hora de um registro de cuidado de forma unica e
 * deterministica, no padrao `dd/mm/yyyy` (e `dd/mm/yyyy • HH:mm` quando
 * houver horario).
 *
 * - `date` ausente/vazia ou invalida (nao parseavel como data) retorna o
 *   fallback `"-"`, sem lancar excecao.
 * - `time` ausente/nulo/vazio faz com que apenas a data seja retornada,
 *   sem separador.
 * - `time` no formato `HH:mm` ou `HH:mm:ss` e normalizado para `HH:mm`.
 */
export function formatRecordDateTime(
  date?: string | null,
  time?: string | null,
): string {
  if (!date) {
    return FALLBACK;
  }

  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(date);
  if (!match) {
    return FALLBACK;
  }

  const [, year, month, day] = match;
  const parsed = new Date(Number(year), Number(month) - 1, Number(day));
  if (
    Number.isNaN(parsed.getTime()) ||
    parsed.getFullYear() !== Number(year) ||
    parsed.getMonth() !== Number(month) - 1 ||
    parsed.getDate() !== Number(day)
  ) {
    return FALLBACK;
  }

  const formattedDate = `${day}/${month}/${year}`;

  if (!time) {
    return formattedDate;
  }

  const formattedTime = time.slice(0, 5);
  return `${formattedDate} • ${formattedTime}`;
}

const MINUTE_MS = 60 * 1000;
const HOUR_MS = 60 * MINUTE_MS;
const DAY_MS = 24 * HOUR_MS;
const RELATIVE_THRESHOLD_MS = 7 * DAY_MS;

function parseRecordDateTime(date: string, time?: string | null): Date | null {
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(date);
  if (!match) {
    return null;
  }

  const [, year, month, day] = match;
  let hours = 0;
  let minutes = 0;
  let seconds = 0;
  if (time) {
    const timeMatch = /^(\d{2}):(\d{2})(?::(\d{2}))?/.exec(time);
    if (timeMatch) {
      hours = Number(timeMatch[1]);
      minutes = Number(timeMatch[2]);
      seconds = timeMatch[3] ? Number(timeMatch[3]) : 0;
    }
  }

  const parsed = new Date(
    Number(year),
    Number(month) - 1,
    Number(day),
    hours,
    minutes,
    seconds,
  );
  if (
    Number.isNaN(parsed.getTime()) ||
    parsed.getFullYear() !== Number(year) ||
    parsed.getMonth() !== Number(month) - 1 ||
    parsed.getDate() !== Number(day)
  ) {
    return null;
  }

  return parsed;
}

/**
 * Formata a data/hora de um registro de cuidado como texto relativo ao
 * instante atual (ex.: "ha 2 horas", "ha 1 dia", "agora mesmo"), no mesmo
 * espirito do restante do app (deterministico, sem lancar excecao).
 *
 * - `date` ausente/invalida retorna o fallback `"-"`.
 * - Diferencas menores que 1 minuto (passado ou futuro) retornam
 *   `"agora mesmo"`.
 * - Diferencas de minutos/horas/dias usam singular/plural em portugues
 *   ("ha 1 minuto" vs "ha 2 minutos").
 * - Registros no futuro usam o prefixo "em" no lugar de "ha".
 * - Diferencas de 7 dias ou mais retornam a data absoluta formatada por
 *   `formatRecordDateTime`, para nao exibir relativos pouco uteis como
 *   "ha 42 dias".
 * - `now` e opcional (default: instante atual) para permitir testes
 *   deterministicos.
 */
export function formatRelativeTime(
  date?: string | null,
  time?: string | null,
  now: Date = new Date(),
): string {
  if (!date) {
    return FALLBACK;
  }

  const target = parseRecordDateTime(date, time);
  if (!target) {
    return FALLBACK;
  }

  const diffMs = now.getTime() - target.getTime();
  const isFuture = diffMs < 0;
  const absDiffMs = Math.abs(diffMs);

  if (absDiffMs < MINUTE_MS) {
    return 'agora mesmo';
  }

  if (absDiffMs >= RELATIVE_THRESHOLD_MS) {
    return formatRecordDateTime(date, time);
  }

  let value: number;
  let unit: string;
  if (absDiffMs < HOUR_MS) {
    value = Math.floor(absDiffMs / MINUTE_MS);
    unit = value === 1 ? 'minuto' : 'minutos';
  } else if (absDiffMs < DAY_MS) {
    value = Math.floor(absDiffMs / HOUR_MS);
    unit = value === 1 ? 'hora' : 'horas';
  } else {
    value = Math.floor(absDiffMs / DAY_MS);
    unit = value === 1 ? 'dia' : 'dias';
  }

  return isFuture ? `em ${value} ${unit}` : `ha ${value} ${unit}`;
}
