import { readFileSync } from 'fs';
import path from 'path';

/**
 * Card #76 (Trello): pedir permissao de microfone ao usuario.
 *
 * app.json precisa declarar as strings de justificativa (iOS) e a
 * permissao de gravacao de audio (Android) para que o app possa usar
 * o microfone (ditado de observacoes) sem ser rejeitado nas lojas e
 * sem crashar em runtime por falta de permissao configurada.
 */
const APP_JSON_PATH = path.resolve(__dirname, '..', '..', 'app.json');

function readAppJson(): any {
  const raw = readFileSync(APP_JSON_PATH, 'utf-8');
  return JSON.parse(raw);
}

describe('app.json - permissao de microfone', () => {
  const appJson = readAppJson();

  it('declara NSMicrophoneUsageDescription no ios.infoPlist em PT-BR', () => {
    const description = appJson.expo?.ios?.infoPlist?.NSMicrophoneUsageDescription;
    expect(typeof description).toBe('string');
    expect(description.length).toBeGreaterThan(0);
    expect(description.toLowerCase()).toMatch(/microfone/);
  });

  it('declara NSSpeechRecognitionUsageDescription no ios.infoPlist em PT-BR', () => {
    const description = appJson.expo?.ios?.infoPlist?.NSSpeechRecognitionUsageDescription;
    expect(typeof description).toBe('string');
    expect(description.length).toBeGreaterThan(0);
    expect(description.toLowerCase()).toMatch(/(voz|fala|ditar|reconhecimento)/);
  });

  it('inclui android.permission.RECORD_AUDIO nas permissions do Android', () => {
    const permissions = appJson.expo?.android?.permissions;
    expect(Array.isArray(permissions)).toBe(true);
    expect(permissions).toContain('android.permission.RECORD_AUDIO');
  });
});
