import fs from 'fs';
import path from 'path';

/**
 * Testes estaticos (regex sobre o conteudo dos arquivos) para o item da tarefa #105:
 * "Redesenhar PasswordResetScreen e alinhar navegacao entre Login/Register/PasswordReset".
 *
 * Garante que:
 *  - O AuthStack.Navigator em RootNavigator.tsx continua registrando exatamente as
 *    rotas 'Login', 'Register' e 'PasswordReset'.
 *  - LoginScreen, RegisterScreen e PasswordResetScreen possuem, cada uma, pelo menos
 *    uma chamada navigation.navigate para as outras duas rotas do fluxo de auth.
 */

const ROOT_NAVIGATOR_PATH = path.resolve(__dirname, '../RootNavigator.tsx');
const LOGIN_SCREEN_PATH = path.resolve(__dirname, '../../screens/LoginScreen.tsx');
const REGISTER_SCREEN_PATH = path.resolve(__dirname, '../../screens/RegisterScreen.tsx');
const PASSWORD_RESET_SCREEN_PATH = path.resolve(__dirname, '../../screens/PasswordResetScreen.tsx');

function readFile(filePath: string): string {
  return fs.readFileSync(filePath, 'utf-8');
}

/** Extrai o bloco de codigo do AuthStack.Navigator (entre a abertura e o fechamento da tag). */
function extractAuthStackNavigatorBlock(rootNavigatorSource: string): string {
  const match = rootNavigatorSource.match(
    /<AuthStack\.Navigator[\s\S]*?<\/AuthStack\.Navigator>/
  );
  if (!match) {
    throw new Error('Nao foi possivel localizar o bloco <AuthStack.Navigator>...</AuthStack.Navigator>');
  }
  return match[0];
}

/** Verifica se o arquivo contem uma chamada navigation.navigate('<routeName>', ...). */
function hasNavigateCallTo(source: string, routeName: string): boolean {
  const pattern = new RegExp(
    `navigation\\.navigate\\(\\s*['"]${routeName}['"]`
  );
  return pattern.test(source);
}

describe('AuthStack.Navigator (RootNavigator.tsx)', () => {
  const rootNavigatorSource = readFile(ROOT_NAVIGATOR_PATH);
  const authStackBlock = extractAuthStackNavigatorBlock(rootNavigatorSource);

  it.each(['Login', 'Register', 'PasswordReset'])(
    'registra a rota "%s" com <AuthStack.Screen name="%s" .../>',
    (routeName) => {
      const screenPattern = new RegExp(
        `<AuthStack\\.Screen\\s+name=['"]${routeName}['"]`
      );
      expect(authStackBlock).toMatch(screenPattern);
    }
  );
});

describe('Navegacao fluida entre Login, Register e PasswordReset', () => {
  it('LoginScreen navega para Register e para PasswordReset', () => {
    const source = readFile(LOGIN_SCREEN_PATH);
    expect(hasNavigateCallTo(source, 'Register')).toBe(true);
    expect(hasNavigateCallTo(source, 'PasswordReset')).toBe(true);
  });

  it('RegisterScreen navega para Login e para PasswordReset', () => {
    const source = readFile(REGISTER_SCREEN_PATH);
    expect(hasNavigateCallTo(source, 'Login')).toBe(true);
    expect(hasNavigateCallTo(source, 'PasswordReset')).toBe(true);
  });

  it('PasswordResetScreen navega para Login e para Register', () => {
    const source = readFile(PASSWORD_RESET_SCREEN_PATH);
    expect(hasNavigateCallTo(source, 'Login')).toBe(true);
    expect(hasNavigateCallTo(source, 'Register')).toBe(true);
  });
});
