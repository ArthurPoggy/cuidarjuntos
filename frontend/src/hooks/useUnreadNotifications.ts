import { useCallback, useEffect, useRef, useState } from 'react';
import { AppState } from 'react-native';
import { notificationsApi } from '../api/endpoints';

const POLL_INTERVAL_MS = 60_000;

/**
 * Mantém a contagem de notificações não lidas do usuário autenticado.
 *
 * Busca o `count` da resposta paginada de `/notifications/?unread=true`,
 * atualiza periodicamente (polling) e refaz a busca quando o app volta para o
 * primeiro plano. Falhas são silenciosas (mantém o último valor conhecido) para
 * não poluir a UI do Header.
 */
export function useUnreadNotifications(enabled: boolean = true) {
  const [count, setCount] = useState(0);
  const mounted = useRef(true);

  const refresh = useCallback(async () => {
    if (!enabled) return;
    try {
      const { data } = await notificationsApi.unread();
      if (mounted.current) setCount(data.count ?? 0);
    } catch {
      // Silencioso: preserva o último valor para não piscar erro no Header.
    }
  }, [enabled]);

  useEffect(() => {
    mounted.current = true;
    if (!enabled) {
      setCount(0);
      return;
    }

    refresh();
    const interval = setInterval(refresh, POLL_INTERVAL_MS);

    const sub = AppState.addEventListener('change', (state) => {
      if (state === 'active') refresh();
    });

    return () => {
      mounted.current = false;
      clearInterval(interval);
      sub.remove();
    };
  }, [enabled, refresh]);

  return { count, refresh };
}
