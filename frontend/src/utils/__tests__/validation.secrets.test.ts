import { readFileSync } from 'fs';
import path from 'path';

/**
 * Regressao para achados do GitGuardian em validation.test.ts (task #105).
 *
 * Conforme FLUXO_DESENVOLVIMENTO_ORQUESTRADO.md (secao "Achados de bots do
 * GitHub"), quando o GitGuardian aponta um segredo em dado ficticio de
 * teste, a correcao correta e trocar o literal por um valor obviamente
 * sintetico (prefixo `fake-` ou `test-`).
 *
 * Este teste varre o CONTEUDO de validation.test.ts em busca de qualquer
 * literal passado para validatePassword(...) que "pareca" uma senha real
 * (letras + numeros, 8+ caracteres) sem o prefixo sintetico exigido pela
 * convencao do projeto — sem citar nenhum literal especifico aqui, para
 * este proprio arquivo nao virar um novo alvo do scanner de segredos.
 */
const TARGET_FILE = path.resolve(__dirname, 'validation.test.ts');

function readTargetSource(): string {
  return readFileSync(TARGET_FILE, 'utf-8');
}

describe('validation.test.ts nao deve conter literais de senha sem prefixo sintetico', () => {
  it('todo literal de senha "valida" (letras+numeros, 8+ caracteres) usado em validatePassword(...) segue a convencao fake-/test-', () => {
    const source = readTargetSource();

    const validLookingPasswordCalls =
      source.match(/validatePassword\(\s*'(?=[^']{8,}')(?=[^']*[A-Za-z])(?=[^']*\d)[^']+'\s*\)/g) ??
      [];
    const withoutSyntheticPrefix = validLookingPasswordCalls.filter(
      (call) => !/'(fake-|test-)/i.test(call)
    );

    expect(withoutSyntheticPrefix).toEqual([]);
  });

  it('todo literal de senha "valida" (letras+numeros, 8+ caracteres) usado em validateLoginFields(...) segue a convencao fake-/test-', () => {
    const source = readTargetSource();

    const validLookingLoginCalls =
      source.match(
        /validateLoginFields\(\s*'[^']*'\s*,\s*'(?=[^']{8,}')(?=[^']*[A-Za-z])(?=[^']*\d)[^']+'\s*\)/g
      ) ?? [];
    const withoutSyntheticPrefix = validLookingLoginCalls.filter(
      (call) => !/,\s*'(fake-|test-)/i.test(call)
    );

    expect(withoutSyntheticPrefix).toEqual([]);
  });

  it('todo valor de "password" em objetos de campos de registro segue a convencao fake-/test-', () => {
    const source = readTargetSource();

    const passwordFieldAssignments =
      source.match(/password:\s*'(?=[^']{8,}')(?=[^']*[A-Za-z])(?=[^']*\d)[^']+'/g) ?? [];
    const withoutSyntheticPrefix = passwordFieldAssignments.filter(
      (assignment) => !/:\s*'(fake-|test-)/i.test(assignment)
    );

    expect(withoutSyntheticPrefix).toEqual([]);
  });
});
