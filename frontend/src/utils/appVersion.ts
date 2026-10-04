/**
 * Política de atualização do app: compara a versão instalada com a que o
 * backend publica em GET /app-version/ (ver api/views/app_version.py).
 */
export type UpdateStatus = 'ok' | 'recommended' | 'required';

export interface AppVersionInfo {
  version: string;
  min_supported_version: string;
  update_url: string;
}

/** Compara "X.Y.Z" numericamente: <0 se a<b, 0 se iguais, >0 se a>b. */
export function compareVersions(a: string, b: string): number {
  const pa = a.split('.').map(n => parseInt(n, 10) || 0);
  const pb = b.split('.').map(n => parseInt(n, 10) || 0);
  for (let i = 0; i < Math.max(pa.length, pb.length); i++) {
    const diff = (pa[i] ?? 0) - (pb[i] ?? 0);
    if (diff !== 0) return diff;
  }
  return 0;
}

export function getUpdateStatus(current: string, info: AppVersionInfo): UpdateStatus {
  if (compareVersions(current, info.min_supported_version) < 0) return 'required';
  if (compareVersions(current, info.version) < 0) return 'recommended';
  return 'ok';
}
