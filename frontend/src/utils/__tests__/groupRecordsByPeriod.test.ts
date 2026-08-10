import {
  groupRecordsByPeriod,
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
