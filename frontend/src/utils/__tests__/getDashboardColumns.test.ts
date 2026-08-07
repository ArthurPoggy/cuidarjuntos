import { getDashboardColumns } from '../getDashboardColumns';

/**
 * Tarefa #109 "Deixar o dashboard em grid padrao -> MOBILE":
 * "Extrair calculo de colunas do grid para funcao pura e torna-lo
 * responsivo em runtime".
 *
 * Cobre os limiares de breakpoint exigidos pelo criterio de aceitacao:
 *  - mobile  (<768)       -> 1 coluna
 *  - tablet  (768 - 1023) -> 2 colunas
 *  - desktop (>=1024)     -> 3 colunas
 *
 * `getDashboardColumns` ainda nao existe em
 * frontend/src/utils/getDashboardColumns.ts, entao este arquivo deve falhar
 * por erro de modulo nao encontrado ate a implementacao ser criada.
 */
describe('getDashboardColumns', () => {
  it('retorna 1 coluna para largura mobile (374)', () => {
    expect(getDashboardColumns(374)).toBe(1);
  });

  it('retorna 2 colunas no limiar exato de tablet (768)', () => {
    expect(getDashboardColumns(768)).toBe(2);
  });

  it('retorna 2 colunas no topo do intervalo de tablet (1023)', () => {
    expect(getDashboardColumns(1023)).toBe(2);
  });

  it('retorna 3 colunas no limiar exato de desktop (1024)', () => {
    expect(getDashboardColumns(1024)).toBe(3);
  });

  it('retorna 1 coluna logo abaixo do limiar de tablet (767)', () => {
    expect(getDashboardColumns(767)).toBe(1);
  });

  it('retorna 3 colunas para larguras bem acima do limiar de desktop', () => {
    expect(getDashboardColumns(1920)).toBe(3);
  });
});
