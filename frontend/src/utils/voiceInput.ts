/**
 * Regra de exibição do botão de ditado por voz (MicrophoneButton) em campos
 * de texto: só faz sentido oferecer quando há um reconhecedor de voz
 * disponível (ver `useSpeechToText`) e a plataforma suporta o recurso.
 *
 * A web (react-native-web) fica de fora deliberadamente: o app ainda não tem
 * uma integração de reconhecimento de voz para esse alvo, então expor o
 * botão lá exibiria um recurso que não funciona.
 *
 * Extraída como função pura (em vez de inline no componente) para poder ser
 * testada sem depender de mockar o módulo `Platform` do react-native.
 */
export function isVoiceInputSupported(platformOS: string, recognizerAvailable: boolean): boolean {
  return platformOS !== 'web' && recognizerAvailable;
}

/**
 * Concatena o texto reconhecido por voz ao conteúdo já digitado em um campo,
 * separando por um espaço. Texto vazio/whitespace no campo original é
 * descartado para não deixar um espaço solto na frente do texto ditado.
 */
export function appendSpokenText(current: string, spoken: string): string {
  const trimmedCurrent = current.trim();
  return trimmedCurrent ? `${trimmedCurrent} ${spoken}` : spoken;
}
