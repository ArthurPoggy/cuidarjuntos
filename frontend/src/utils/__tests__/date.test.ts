import { getLocalDateIso, formatAgendaDayLabel } from '../date';

/**
 * Testes para o item da tarefa #110 "Consertar agenda -> MOBILE":
 * "Corrigir bug de fuso horario nos rotulos e agrupamento de dias da
 * agenda (UpcomingScreen)".
 *
 * Hoje `formatDayLabel` (definida inline em
 * frontend/src/screens/UpcomingScreen.tsx) calcula o dia de "hoje"/"amanha"
 * usando `new Date().toISOString().slice(0, 10)`, que retorna a data em UTC,
 * e compara com `dateIso`, que e a data LOCAL enviada pelo backend. Para
 * usuarios em fusos negativos (ex.: America/Sao_Paulo, UTC-3), isso faz com
 * que, proximo a meia-noite local (por volta das 21h-23h59 locais), o "dia
 * UTC" ja tenha avancado para o dia seguinte antes do "dia local" avancar,
 * levando a rotulos ('Hoje'/'Amanha') e agrupamentos errados.
 *
 * Este arquivo testa `frontend/src/utils/date.ts`, um modulo ainda
 * inexistente que deve ser criado pela correcao, extraindo a logica de
 * formatacao/agrupamento de datas da agenda para funcoes puras e testaveis:
 *
 *   - `getLocalDateIso(date?: Date): string` — retorna a data local (nao
 *     UTC) no formato 'yyyy-MM-dd', usando o fuso horario do sistema/relogio
 *     (America/Sao_Paulo no caso do publico-alvo do app).
 *   - `formatAgendaDayLabel(dateIso: string, referenceDate?: Date): string`
 *     — dado um `dateIso` local (formato 'yyyy-MM-dd', como o que vem do
 *     backend) e uma data de referencia (default: `new Date()`), retorna
 *     'Hoje', 'Amanha' ou '<DiaDaSemana>, dd/mm', sempre comparando datas
 *     locais entre si (nunca misturando data local com data UTC).
 *
 * Ate essas funcoes serem criadas, TODOS os testes abaixo falham por erro de
 * modulo nao encontrado ("Cannot find module '../date'") — essa e a falha
 * esperada nesta etapa (somente testes, sem implementacao da correcao).
 */

const ORIGINAL_TZ = process.env.TZ;

describe('utils/date - fuso horario local (America/Sao_Paulo, UTC-3)', () => {
  beforeAll(() => {
    process.env.TZ = 'America/Sao_Paulo';
  });

  afterAll(() => {
    process.env.TZ = ORIGINAL_TZ;
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  describe('getLocalDateIso', () => {
    it('retorna a data local (nao UTC) as 23:50 no fuso local, quando o dia UTC ja avancou', () => {
      // 15/01/2026 23:50 em America/Sao_Paulo (UTC-3) equivale a
      // 16/01/2026 02:50 em UTC. Uma implementacao baseada em
      // `toISOString().slice(0, 10)` retornaria erroneamente '2026-01-16'
      // (o dia UTC), quando o dia local correto ainda e '2026-01-15'.
      jest.useFakeTimers().setSystemTime(new Date('2026-01-16T02:50:00.000Z'));

      expect(getLocalDateIso(new Date())).toBe('2026-01-15');
    });

    it('retorna a data local corretamente as 00:10, logo apos a virada do dia local', () => {
      // 16/01/2026 00:10 em America/Sao_Paulo (UTC-3) equivale a
      // 16/01/2026 03:10 em UTC.
      jest.useFakeTimers().setSystemTime(new Date('2026-01-16T03:10:00.000Z'));

      expect(getLocalDateIso(new Date())).toBe('2026-01-16');
    });
  });

  describe('formatAgendaDayLabel', () => {
    it('rotula como "Hoje" um item as 23:50 locais, mesmo com o dia UTC ja adiantado', () => {
      // Sistema em 15/01/2026 23:50 local == 16/01/2026 02:50 UTC.
      // O backend envia o dateIso do bucket usando a data LOCAL do evento
      // ('2026-01-15'). Comparar isso com `new Date().toISOString()` (que
      // devolveria '2026-01-16') classificaria errado esse item como nao
      // sendo "Hoje".
      jest.useFakeTimers().setSystemTime(new Date('2026-01-16T02:50:00.000Z'));

      expect(formatAgendaDayLabel('2026-01-15')).toBe('Hoje');
    });

    it('nao rotula como "Hoje" o dia que so coincide com a data UTC as 23:50 locais', () => {
      // No mesmo instante do teste acima, o dia UTC e '2026-01-16', mas o
      // dia local ainda e '2026-01-15'. '2026-01-16' deve ser "Amanha" (do
      // ponto de vista local), nunca "Hoje".
      jest.useFakeTimers().setSystemTime(new Date('2026-01-16T02:50:00.000Z'));

      expect(formatAgendaDayLabel('2026-01-16')).not.toBe('Hoje');
      expect(formatAgendaDayLabel('2026-01-16')).toBe('Amanha');
    });

    it('rotula corretamente "Hoje" as 00:10 locais, logo apos a virada do dia', () => {
      jest.useFakeTimers().setSystemTime(new Date('2026-01-16T03:10:00.000Z'));

      expect(formatAgendaDayLabel('2026-01-16')).toBe('Hoje');
    });

    it('rotula corretamente "Amanha" as 00:10 locais', () => {
      jest.useFakeTimers().setSystemTime(new Date('2026-01-16T03:10:00.000Z'));

      expect(formatAgendaDayLabel('2026-01-17')).toBe('Amanha');
    });

    it('nao rotula o dia local anterior como "Hoje" as 00:10, mesmo perto da virada UTC', () => {
      jest.useFakeTimers().setSystemTime(new Date('2026-01-16T03:10:00.000Z'));

      expect(formatAgendaDayLabel('2026-01-15')).not.toBe('Hoje');
    });

    it('formata datas fora de hoje/amanha com dia da semana local e dd/mm', () => {
      // Sistema em 15/01/2026 23:50 local (dia local = 2026-01-15, uma
      // quinta-feira). 2026-01-20 e uma terca-feira e nao deve ser afetado
      // pela conversao para UTC.
      jest.useFakeTimers().setSystemTime(new Date('2026-01-16T02:50:00.000Z'));

      expect(formatAgendaDayLabel('2026-01-20')).toBe('Terca, 20/01');
    });
  });
});
