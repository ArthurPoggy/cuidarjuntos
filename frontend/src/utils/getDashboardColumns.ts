/**
 * Calcula o numero de colunas do grid do dashboard a partir da largura
 * disponivel da janela, seguindo os breakpoints padrao do app:
 *
 *  - mobile  (<768)       -> 1 coluna
 *  - tablet  (768 - 1023) -> 2 colunas
 *  - desktop (>=1024)     -> 3 colunas
 *
 * Funcao pura: nao depende de `Dimensions.get`/estado de modulo, permitindo
 * recalculo em runtime (ex.: junto com `useWindowDimensions`) a cada render.
 */
export function getDashboardColumns(width: number): number {
  if (width >= 1024) return 3;
  if (width >= 768) return 2;
  return 1;
}
