import { compareVersions, getUpdateStatus } from '../appVersion';

const info = (version: string, min: string) => ({
  version,
  min_supported_version: min,
  update_url: '',
});

describe('compareVersions', () => {
  it('compara numericamente, não por texto', () => {
    expect(compareVersions('1.10.0', '1.9.0')).toBeGreaterThan(0);
    expect(compareVersions('1.0.0', '1.0.1')).toBeLessThan(0);
    expect(compareVersions('2.0.0', '2.0.0')).toBe(0);
  });

  it('trata segmentos ausentes como zero', () => {
    expect(compareVersions('1.0', '1.0.0')).toBe(0);
  });
});

describe('getUpdateStatus', () => {
  it('ok quando está na versão atual ou à frente', () => {
    expect(getUpdateStatus('1.2.0', info('1.2.0', '1.0.0'))).toBe('ok');
    expect(getUpdateStatus('1.3.0', info('1.2.0', '1.0.0'))).toBe('ok');
  });

  it('recomendada quando há versão nova mas a atual ainda é suportada', () => {
    expect(getUpdateStatus('1.1.0', info('1.2.0', '1.0.0'))).toBe('recommended');
  });

  it('obrigatória quando está abaixo da versão mínima suportada', () => {
    expect(getUpdateStatus('1.0.0', info('1.2.0', '1.1.0'))).toBe('required');
  });
});
