import fs from 'fs';
import path from 'path';

/**
 * Testes estaticos (regex sobre o conteudo dos arquivos) para a tarefa #79
 * "Filtrar exportacao por categoria de cuidado", subtask 1: criar a tela
 * ExportScreen e dar acesso a ela pela navegacao.
 *
 * Garante que:
 *  - RootNavigator.tsx registra a rota 'Export' dentro do MainStack.Navigator,
 *    apontando para o componente ExportScreen.
 *  - Header.tsx possui um item de menu que navega para a rota 'Export'.
 */

const ROOT_NAVIGATOR_PATH = path.resolve(__dirname, '../RootNavigator.tsx');
const HEADER_PATH = path.resolve(__dirname, '../../components/Header.tsx');

function readFile(filePath: string): string {
  return fs.readFileSync(filePath, 'utf-8');
}

/** Extrai o bloco de codigo do MainStack.Navigator (entre abertura e fechamento da tag). */
function extractMainStackNavigatorBlock(rootNavigatorSource: string): string {
  const match = rootNavigatorSource.match(
    /<MainStack\.Navigator[\s\S]*?<\/MainStack\.Navigator>/
  );
  if (!match) {
    throw new Error('Nao foi possivel localizar o bloco <MainStack.Navigator>...</MainStack.Navigator>');
  }
  return match[0];
}

describe('MainStack.Navigator (RootNavigator.tsx) - rota Export', () => {
  it('importa ExportScreen a partir de ../screens/ExportScreen', () => {
    const rootNavigatorSource = readFile(ROOT_NAVIGATOR_PATH);
    expect(rootNavigatorSource).toMatch(
      /import\s+ExportScreen\s+from\s+['"]\.\.\/screens\/ExportScreen['"]/
    );
  });

  it('registra a rota "Export" com <MainStack.Screen name="Export" component={ExportScreen} />', () => {
    const rootNavigatorSource = readFile(ROOT_NAVIGATOR_PATH);
    const mainStackBlock = extractMainStackNavigatorBlock(rootNavigatorSource);
    expect(mainStackBlock).toMatch(/<MainStack\.Screen\s+name=['"]Export['"]/);
    expect(mainStackBlock).toMatch(/component=\{ExportScreen\}/);
  });
});

describe('Header.tsx - ponto de entrada de navegacao para Export', () => {
  it('possui uma chamada navigation.navigate(\'Export\') no menu', () => {
    const headerSource = readFile(HEADER_PATH);
    expect(headerSource).toMatch(/navigation\.navigate\(\s*['"]Export['"]/);
  });
});
