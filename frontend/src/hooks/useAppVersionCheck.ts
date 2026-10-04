import { useQuery } from '@tanstack/react-query';
import Constants from 'expo-constants';
import { appVersionApi } from '../api/endpoints';
import { getUpdateStatus, type AppVersionInfo, type UpdateStatus } from '../utils/appVersion';

/** Versão deste build (vem de `expo.version` no app.json). */
export const CURRENT_APP_VERSION = Constants.expoConfig?.version ?? '0.0.0';

/**
 * Consulta a versão publicada pelo backend e diz se este app precisa de
 * atualização. Falha aberta: se a consulta falhar (rede/servidor), o app segue
 * normalmente — nunca bloqueia o usuário por não conseguir checar.
 */
export function useAppVersionCheck(): { status: UpdateStatus; info?: AppVersionInfo } {
  const { data } = useQuery({
    queryKey: ['app-version'],
    queryFn: async () => (await appVersionApi.get()).data,
    staleTime: 1000 * 60 * 60,
    retry: false,
  });
  if (!data) return { status: 'ok' };
  return { status: getUpdateStatus(CURRENT_APP_VERSION, data), info: data };
}
