import { isVoiceInputSupported, appendSpokenText } from '../voiceInput';

describe('isVoiceInputSupported', () => {
  it('fica oculto em Platform.OS === "web" mesmo com reconhecedor disponível', () => {
    expect(isVoiceInputSupported('web', true)).toBe(false);
  });

  it('fica oculto quando não há reconhecedor de voz disponível, mesmo fora da web', () => {
    expect(isVoiceInputSupported('ios', false)).toBe(false);
    expect(isVoiceInputSupported('android', false)).toBe(false);
  });

  it('fica visível em iOS/Android quando há reconhecedor disponível', () => {
    expect(isVoiceInputSupported('ios', true)).toBe(true);
    expect(isVoiceInputSupported('android', true)).toBe(true);
  });
});

describe('appendSpokenText', () => {
  it('concatena o texto ditado ao conteúdo já existente, separado por espaço', () => {
    expect(appendSpokenText('Texto existente', 'texto ditado')).toBe('Texto existente texto ditado');
  });

  it('usa apenas o texto ditado quando o campo está vazio', () => {
    expect(appendSpokenText('', 'texto ditado')).toBe('texto ditado');
  });

  it('trata conteúdo apenas com espaços como vazio', () => {
    expect(appendSpokenText('   ', 'texto ditado')).toBe('texto ditado');
  });
});
