import fs from 'fs';
import path from 'path';
import { colors } from '../../theme';

/**
 * Testes estaticos (regex sobre o texto-fonte) para o item da tarefa #105:
 * "Checklist final de acessibilidade e compatibilidade iOS/Android".
 *
 * Cobre, para as tres telas de autenticacao (LoginScreen, RegisterScreen,
 * PasswordResetScreen):
 *  - Todo <TextInput> possui a prop accessibilityLabel definida (contagem de
 *    TextInput === contagem de accessibilityLabel dentro de cada bloco de TextInput).
 *    Este e o criterio de aceitacao verificavel exigido pelo card.
 *  - Todo <TouchableOpacity> "relevante" (acionavel) possui accessibilityRole
 *    e accessibilityLabel, conforme descrito no item.
 *  - Contraste de cores conforme theme.ts: pares texto/fundo efetivamente
 *    usados nas telas (via colors.* de theme.ts) atendem WCAG AA (>= 4.5:1).
 *  - Area de toque minima (hitSlop ou padding) nos botoes: todo
 *    <TouchableOpacity> possui a prop hitSlop OU um estilo (via
 *    styles.<chave> referenciado no proprio elemento) com padding/minHeight/
 *    minWidth definidos.
 *  - SafeAreaView cobre as tres telas (import de
 *    'react-native-safe-area-context' e uso como elemento raiz do retorno).
 */

const SCREENS_DIR = path.resolve(__dirname, '..');

const SCREEN_FILES = {
  LoginScreen: path.join(SCREENS_DIR, 'LoginScreen.tsx'),
  RegisterScreen: path.join(SCREENS_DIR, 'RegisterScreen.tsx'),
  PasswordResetScreen: path.join(SCREENS_DIR, 'PasswordResetScreen.tsx'),
} as const;

function readFile(filePath: string): string {
  return fs.readFileSync(filePath, 'utf-8');
}

/**
 * Extrai o texto de cada tag de abertura de um componente JSX, do "<Nome" ate
 * o primeiro ">" que realmente fecha a tag (self-closing ou nao). O
 * lookbehind negativo "(?<!=)" evita parar precocemente em arrow functions
 * inline (ex.: onPress={() => ...}), cujo "=>" contem um ">" que nao fecha a
 * tag JSX.
 */
function extractOpeningTags(source: string, componentName: string): string[] {
  const pattern = new RegExp(`<${componentName}[\\s\\S]*?(?<!=)>`, 'g');
  return source.match(pattern) ?? [];
}

function countPropOccurrences(tags: string[], propName: string): number {
  return tags.filter((tag) => tag.includes(`${propName}=`)).length;
}

describe('Acessibilidade das telas de autenticacao - TextInput', () => {
  it.each(Object.entries(SCREEN_FILES))(
    '%s: todo TextInput possui accessibilityLabel (contagem de TextInput === contagem de accessibilityLabel)',
    (_screenName, filePath) => {
      const source = readFile(filePath);
      const textInputTags = extractOpeningTags(source, 'TextInput');

      // Sanidade: a tela precisa ter pelo menos um campo de texto.
      expect(textInputTags.length).toBeGreaterThan(0);

      const withAccessibilityLabel = countPropOccurrences(textInputTags, 'accessibilityLabel');

      expect(withAccessibilityLabel).toBe(textInputTags.length);
    }
  );
});

describe('Acessibilidade das telas de autenticacao - TouchableOpacity', () => {
  it.each(Object.entries(SCREEN_FILES))(
    '%s: todo TouchableOpacity possui accessibilityRole="button"',
    (_screenName, filePath) => {
      const source = readFile(filePath);
      const touchableTags = extractOpeningTags(source, 'TouchableOpacity');

      expect(touchableTags.length).toBeGreaterThan(0);

      const withAccessibilityRole = countPropOccurrences(touchableTags, 'accessibilityRole');

      expect(withAccessibilityRole).toBe(touchableTags.length);
    }
  );

  it.each(Object.entries(SCREEN_FILES))(
    '%s: todo TouchableOpacity possui accessibilityLabel',
    (_screenName, filePath) => {
      const source = readFile(filePath);
      const touchableTags = extractOpeningTags(source, 'TouchableOpacity');

      expect(touchableTags.length).toBeGreaterThan(0);

      const withAccessibilityLabel = countPropOccurrences(touchableTags, 'accessibilityLabel');

      expect(withAccessibilityLabel).toBe(touchableTags.length);
    }
  );
});

describe('KeyboardAvoidingView com comportamento distinto iOS/Android', () => {
  it.each(Object.entries(SCREEN_FILES))(
    '%s: KeyboardAvoidingView usa behavior condicional por Platform.OS (padding no iOS, undefined no Android)',
    (_screenName, filePath) => {
      const source = readFile(filePath);

      const behaviorPattern =
        /behavior=\{\s*Platform\.OS\s*===\s*['"]ios['"]\s*\?\s*['"]padding['"]\s*:\s*undefined\s*\}/;

      expect(source).toMatch(behaviorPattern);
    }
  );
});

describe('SafeAreaView cobre as telas de autenticacao (iOS/Android)', () => {
  it.each(Object.entries(SCREEN_FILES))(
    '%s: importa SafeAreaView de react-native-safe-area-context',
    (_screenName, filePath) => {
      const source = readFile(filePath);

      const importPattern =
        /import\s*\{\s*SafeAreaView\s*\}\s*from\s*['"]react-native-safe-area-context['"]/;

      expect(source).toMatch(importPattern);
    }
  );

  it.each(Object.entries(SCREEN_FILES))(
    '%s: usa <SafeAreaView> como elemento raiz do return, envolvendo o restante da tela',
    (_screenName, filePath) => {
      const source = readFile(filePath);

      // O "return (" deve ser seguido (ignorando espacos/quebras de linha) pela
      // abertura de <SafeAreaView ...>, e deve existir um </SafeAreaView> de
      // fechamento correspondente mais adiante no JSX.
      const returnThenSafeArea = /return\s*\(\s*<SafeAreaView[\s>]/;
      expect(source).toMatch(returnThenSafeArea);
      expect(source).toMatch(/<\/SafeAreaView>/);

      // O SafeAreaView deve conter o KeyboardAvoidingView (garante que a area
      // segura envolve o comportamento de teclado especifico da plataforma).
      const safeAreaIdx = source.search(/<SafeAreaView[\s>]/);
      const safeAreaCloseIdx = source.indexOf('</SafeAreaView>');
      const keyboardAvoidingIdx = source.indexOf('<KeyboardAvoidingView');

      expect(safeAreaIdx).toBeGreaterThanOrEqual(0);
      expect(safeAreaCloseIdx).toBeGreaterThan(safeAreaIdx);
      expect(keyboardAvoidingIdx).toBeGreaterThan(safeAreaIdx);
      expect(keyboardAvoidingIdx).toBeLessThan(safeAreaCloseIdx);
    }
  );
});

describe('Area de toque minima (hitSlop ou padding) nos botoes', () => {
  /**
   * Extrai, com contagem balanceada de chaves, o corpo do objeto de estilo
   * associado a uma chave dentro de "StyleSheet.create({ ... })". Necessario
   * porque alguns blocos (ex.: "card") tem objetos aninhados
   * (ex.: shadowOffset: { width, height }), o que quebraria uma regex
   * "nao-gulosa" simples baseada em "}," .
   */
  function getStyleBlockSource(source: string, styleKey: string): string | null {
    const keyRegex = new RegExp(`[{,]\\s*${styleKey}\\s*:\\s*\\{`);
    const match = keyRegex.exec(source);
    if (!match) return null;

    let idx = match.index + match[0].length;
    let depth = 1;
    const start = idx;
    while (depth > 0 && idx < source.length) {
      const ch = source[idx];
      if (ch === '{') depth++;
      else if (ch === '}') depth--;
      idx++;
    }
    return source.slice(start, idx - 1);
  }

  function hasMinimumTouchArea(source: string, touchableTag: string): boolean {
    if (/hitSlop\s*=/.test(touchableTag)) {
      return true;
    }

    const referencedStyleKeys = Array.from(touchableTag.matchAll(/styles\.(\w+)/g)).map(
      (m) => m[1]
    );

    if (referencedStyleKeys.length === 0) {
      return false;
    }

    const combinedStyleSource = referencedStyleKeys
      .map((key) => getStyleBlockSource(source, key) ?? '')
      .join('\n');

    return /(padding|minHeight|minWidth)\s*:/.test(combinedStyleSource);
  }

  it.each(Object.entries(SCREEN_FILES))(
    '%s: todo TouchableOpacity possui hitSlop ou um estilo com padding/minHeight/minWidth',
    (_screenName, filePath) => {
      const source = readFile(filePath);
      const touchableTags = extractOpeningTags(source, 'TouchableOpacity');

      expect(touchableTags.length).toBeGreaterThan(0);

      const offenders = touchableTags.filter((tag) => !hasMinimumTouchArea(source, tag));

      expect(offenders).toEqual([]);
    }
  );
});

describe('Contraste de cores conforme theme.ts (WCAG AA, minimo 4.5:1 para texto normal)', () => {
  function hexToRgb(hex: string): [number, number, number] {
    const normalized = hex.replace('#', '');
    const r = parseInt(normalized.substring(0, 2), 16);
    const g = parseInt(normalized.substring(2, 4), 16);
    const b = parseInt(normalized.substring(4, 6), 16);
    return [r, g, b];
  }

  function channelToLinear(channel: number): number {
    const cs = channel / 255;
    return cs <= 0.03928 ? cs / 12.92 : Math.pow((cs + 0.055) / 1.055, 2.4);
  }

  function relativeLuminance(hex: string): number {
    const [r, g, b] = hexToRgb(hex);
    const [rl, gl, bl] = [channelToLinear(r), channelToLinear(g), channelToLinear(b)];
    return 0.2126 * rl + 0.7152 * gl + 0.0722 * bl;
  }

  function contrastRatio(hexA: string, hexB: string): number {
    const lA = relativeLuminance(hexA);
    const lB = relativeLuminance(hexB);
    const lighter = Math.max(lA, lB);
    const darker = Math.min(lA, lB);
    return (lighter + 0.05) / (darker + 0.05);
  }

  // Pares texto/fundo de theme.ts efetivamente usados nas tres telas de
  // autenticacao (labels, textos de botao, links, mensagens de erro e texto
  // muted/placeholder), com o minimo exigido pelo WCAG 2.1 AA para texto de
  // tamanho normal.
  const WCAG_AA_NORMAL_TEXT = 4.5;

  const colorPairs: Array<{ description: string; fg: string; bg: string; minRatio: number }> = [
    {
      description: 'Texto principal (colors.text) sobre fundo da tela (colors.background)',
      fg: colors.text,
      bg: colors.background,
      minRatio: WCAG_AA_NORMAL_TEXT,
    },
    {
      description: 'Texto secundario (colors.textSecondary) sobre fundo da tela (colors.background)',
      fg: colors.textSecondary,
      bg: colors.background,
      minRatio: WCAG_AA_NORMAL_TEXT,
    },
    {
      description: 'Texto de botao (colors.textInverse) sobre botao primario (colors.primary)',
      fg: colors.textInverse,
      bg: colors.primary,
      minRatio: WCAG_AA_NORMAL_TEXT,
    },
    {
      description: 'Texto de erro (colors.danger) sobre caixa de erro (#FEF2F2, usada nas 3 telas)',
      fg: colors.danger,
      bg: '#FEF2F2',
      minRatio: WCAG_AA_NORMAL_TEXT,
    },
    {
      description: 'Texto de link/acao secundaria (colors.primary) sobre o card (colors.surface)',
      fg: colors.primary,
      bg: colors.surface,
      minRatio: WCAG_AA_NORMAL_TEXT,
    },
    {
      description: 'Texto muted/placeholder (colors.textMuted) sobre o card (colors.surface)',
      fg: colors.textMuted,
      bg: colors.surface,
      minRatio: WCAG_AA_NORMAL_TEXT,
    },
    {
      description: 'Texto muted/placeholder (colors.textMuted) sobre fundo da tela (colors.background)',
      fg: colors.textMuted,
      bg: colors.background,
      minRatio: WCAG_AA_NORMAL_TEXT,
    },
  ];

  it.each(colorPairs)('$description deve ter contraste >= $minRatio:1 (WCAG AA)', ({ fg, bg, minRatio }) => {
    const ratio = contrastRatio(fg, bg);
    expect(ratio).toBeGreaterThanOrEqual(minRatio);
  });
});
