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
