import { renderHook, act } from '@testing-library/react-native';
import {
  useSpeechToText,
  setSpeechRecognizer,
  type SpeechRecognizer,
  type SpeechRecognizerHandlers,
} from '../useSpeechToText';

/**
 * Testes automatizados para o card #70 ("Testes automatizados de
 * fallback/erro do reconhecimento de voz"). A tarefa original do Trello
 * pedia QA manual em iOS/Android/Web, algo que este agente não pode
 * executar fisicamente -- em vez disso, cobrimos aqui os mesmos cenários de
 * fallback/erro de forma automatizada:
 *
 *   - `isAvailable()` false (web/dispositivo sem suporte): `start()` falha
 *     graciosamente com status 'error', sem chamar o reconhecedor.
 *   - Permissão de microfone negada: `start()` vai para 'error' com a
 *     mensagem apropriada.
 *   - `requestPermission()` rejeitando (erro nativo em vez de `false`):
 *     tratado como falha, não propaga exceção não capturada.
 *
 * A verificação manual em dispositivo real (iOS/Android físicos) continua
 * pendente de QA humano -- não é um objetivo automatizável.
 */

function buildRecognizer(overrides: Partial<SpeechRecognizer> = {}): SpeechRecognizer {
  return {
    isAvailable: () => true,
    requestPermission: async () => true,
    start: async () => {},
    stop: async () => {},
    ...overrides,
  };
}

describe('useSpeechToText - fallback e erros', () => {
  afterEach(() => {
    // Restaura o stub padrão para não vazar reconhecedor entre testes.
    setSpeechRecognizer(buildRecognizer({ isAvailable: () => false }));
  });

  it('isAvailable reflete false quando não há reconhecedor suportado (ex.: web)', async () => {
    setSpeechRecognizer(buildRecognizer({ isAvailable: () => false }));

    const { result } = await renderHook(() => useSpeechToText());

    expect(result.current.isAvailable).toBe(false);
  });

  it('start() falha graciosamente sem chamar o reconhecedor quando isAvailable() é false', async () => {
    const startSpy = jest.fn();
    setSpeechRecognizer(
      buildRecognizer({ isAvailable: () => false, start: async () => startSpy() })
    );

    const onError = jest.fn();
    const { result } = await renderHook(() => useSpeechToText(onError));

    await act(async () => {
      await result.current.start(jest.fn());
    });

    expect(startSpy).not.toHaveBeenCalled();
    expect(result.current.status).toBe('error');
    expect(onError).toHaveBeenCalledTimes(1);
    expect((onError.mock.calls[0][0] as Error).message).toMatch(/não está disponível/i);
  });

  it('vai para o status error quando a permissão de microfone é negada', async () => {
    setSpeechRecognizer(
      buildRecognizer({ isAvailable: () => true, requestPermission: async () => false })
    );

    const onError = jest.fn();
    const { result } = await renderHook(() => useSpeechToText(onError));

    await act(async () => {
      await result.current.start(jest.fn());
    });

    expect(result.current.status).toBe('error');
    expect(result.current.isRecording).toBe(false);
    expect((onError.mock.calls[0][0] as Error).message).toMatch(/permissão de microfone negada/i);
  });

  it('trata rejeição de requestPermission() (erro nativo) como falha, sem lançar', async () => {
    const permissionError = new Error('módulo nativo indisponível');
    setSpeechRecognizer(
      buildRecognizer({
        isAvailable: () => true,
        requestPermission: async () => {
          throw permissionError;
        },
      })
    );

    const onError = jest.fn();
    const { result } = await renderHook(() => useSpeechToText(onError));

    await act(async () => {
      await result.current.start(jest.fn());
    });

    expect(result.current.status).toBe('error');
    expect(result.current.error).toBe(permissionError);
    expect(onError).toHaveBeenCalledWith(permissionError);
  });

  it('propaga erro emitido pelo callback onError do adaptador durante a gravação', async () => {
    const recognitionError = new Error('falha no reconhecimento');
    let handlers: SpeechRecognizerHandlers | undefined;
    setSpeechRecognizer(
      buildRecognizer({
        isAvailable: () => true,
        requestPermission: async () => true,
        start: async (h) => {
          handlers = h;
        },
      })
    );

    const onError = jest.fn();
    const { result } = await renderHook(() => useSpeechToText(onError));

    await act(async () => {
      await result.current.start(jest.fn());
    });
    expect(result.current.status).toBe('recording');

    await act(async () => {
      handlers?.onError(recognitionError);
    });

    expect(result.current.status).toBe('error');
    expect(onError).toHaveBeenCalledWith(recognitionError);
  });
});
