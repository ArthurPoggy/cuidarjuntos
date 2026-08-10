import {
  groupRecordsByPeriod,
  groupRecordsByDayAndPeriod,
  getPeriodForTime,
} from '../groupRecordsByPeriod';

describe('getPeriodForTime', () => {
  it('classifica horarios da manha (00:00 - 11:59)', () => {
    expect(getPeriodForTime('00:00')).toBe('morning');
    expect(getPeriodForTime('06:30')).toBe('morning');
    expect(getPeriodForTime('11:59')).toBe('morning');
  });

  it('classifica horarios da tarde (12:00 - 17:59)', () => {
    expect(getPeriodForTime('12:00')).toBe('afternoon');
    expect(getPeriodForTime('15:45')).toBe('afternoon');
    expect(getPeriodForTime('17:59')).toBe('afternoon');
  });

  it('classifica horarios da noite (18:00 - 23:59)', () => {
    expect(getPeriodForTime('18:00')).toBe('evening');
    expect(getPeriodForTime('21:10')).toBe('evening');
    expect(getPeriodForTime('23:59')).toBe('evening');
  });

  it('trata horario ausente/vazio como manha', () => {
    expect(getPeriodForTime(null)).toBe('morning');
    expect(getPeriodForTime(undefined)).toBe('morning');
    expect(getPeriodForTime('')).toBe('morning');
  });
});

describe('groupRecordsByPeriod', () => {
  it('agrupa registros em blocos manha/tarde/noite preservando a ordem interna', () => {
    const records = [
      { id: 1, time: '08:00' },
      { id: 2, time: '14:00' },
      { id: 3, time: '20:00' },
      { id: 4, time: '09:30' },
    ];

    const groups = groupRecordsByPeriod(records);

    expect(groups.map((g) => g.period)).toEqual([
      'morning',
      'afternoon',
      'evening',
    ]);
    expect(groups.map((g) => g.label)).toEqual(['Manhã', 'Tarde', 'Noite']);
    expect(groups[0].records.map((r) => r.id)).toEqual([1, 4]);
    expect(groups[1].records.map((r) => r.id)).toEqual([2]);
    expect(groups[2].records.map((r) => r.id)).toEqual([3]);
  });

  it('omite blocos sem nenhum registro', () => {
    const records = [{ id: 1, time: '10:00' }];
    const groups = groupRecordsByPeriod(records);
    expect(groups).toHaveLength(1);
    expect(groups[0].period).toBe('morning');
  });

  it('retorna lista vazia quando nao ha registros', () => {
    expect(groupRecordsByPeriod([])).toEqual([]);
  });
});

describe('groupRecordsByDayAndPeriod', () => {
  it('agrupa por dia (na ordem em que os dias aparecem) e, dentro de cada dia, por bloco', () => {
    // Simula a ordenacao da API (-date, -time): dias mais recentes primeiro,
    // e dentro de cada dia os horarios mais tarde primeiro.
    const records = [
      { id: 1, date: '2026-08-10', time: '20:00' },
      { id: 2, date: '2026-08-10', time: '08:00' },
      { id: 3, date: '2026-08-09', time: '14:00' },
      { id: 4, date: '2026-08-09', time: '07:00' },
    ];

    const dayGroups = groupRecordsByDayAndPeriod(records);

    expect(dayGroups.map((g) => g.date)).toEqual(['2026-08-10', '2026-08-09']);

    const [day1, day2] = dayGroups;
    expect(day1.periods.map((p) => p.period)).toEqual(['morning', 'evening']);
    expect(day1.periods[0].records.map((r) => r.id)).toEqual([2]);
    expect(day1.periods[1].records.map((r) => r.id)).toEqual([1]);

    expect(day2.periods.map((p) => p.period)).toEqual(['morning', 'afternoon']);
    expect(day2.periods[0].records.map((r) => r.id)).toEqual([4]);
    expect(day2.periods[1].records.map((r) => r.id)).toEqual([3]);
  });

  it('nao mistura registros de dias diferentes no mesmo bloco', () => {
    const records = [
      { id: 1, date: '2026-08-10', time: '08:00' },
      { id: 2, date: '2026-08-09', time: '08:30' },
    ];

    const dayGroups = groupRecordsByDayAndPeriod(records);

    expect(dayGroups).toHaveLength(2);
    expect(dayGroups[0].periods[0].records.map((r) => r.id)).toEqual([1]);
    expect(dayGroups[1].periods[0].records.map((r) => r.id)).toEqual([2]);
  });

  it('com um unico dia, produz um unico grupo cujos blocos equivalem a groupRecordsByPeriod', () => {
    const records = [
      { id: 1, date: '2026-08-10', time: '20:00' },
      { id: 2, date: '2026-08-10', time: '13:00' },
      { id: 3, date: '2026-08-10', time: '08:00' },
    ];

    const dayGroups = groupRecordsByDayAndPeriod(records);
    expect(dayGroups).toHaveLength(1);
    expect(dayGroups[0].date).toBe('2026-08-10');
    expect(dayGroups[0].periods).toEqual(groupRecordsByPeriod(records));
  });

  it('retorna lista vazia quando nao ha registros', () => {
    expect(groupRecordsByDayAndPeriod([])).toEqual([]);
  });
});
