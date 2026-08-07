import React from 'react';
import { StyleSheet, TouchableOpacity } from 'react-native';
import { render, fireEvent, within } from '@testing-library/react-native';
import RecordCreateScreen from '../RecordCreateScreen';
import { recordsApi, medicationsApi } from '../../api/endpoints';

// Tarefa #99 (subtask 4): garante que o formulário "Adicionar remédio"
// (branch MEDICATION de RecordCreateScreen) renderiza sem quebrar tanto em
// Platform.OS = 'ios' quanto em Platform.OS = 'web' (react-native-web), já
// que o app roda nas duas plataformas via Expo, e que os estilos aplicados
// aos elementos-chave do formulário (input de texto, botão de opção,
// botão de submit) ficam registrados via `toMatchSnapshot()` — a técnica
// pedida literalmente pelo AC da subtask 4 ("snapshot tests ... os
// snapshots batem") — em vez de apenas comparar os textos visíveis (o que
// não detectaria estilo hardcoded/quebrado) ou de reafirmar via
// `toMatchObject` um objeto fixo que teria de ser idêntico nas duas
// plataformas.
//
// Cada plataforma grava seu próprio snapshot nomeado (o hint passado a
// `toMatchSnapshot` já inclui, via describe.each, qual Platform.OS gerou o
// valor). Isso é deliberado: se um dia uma ramificação Platform.OS legítima
// e correta passar a existir em RecordCreateScreen/FormField e produzir um
// valor diferente por plataforma, o teste não falha por definição (como
// falharia comparando ambas contra o mesmo objeto esperado) — o snapshot
// daquela plataforma específica só muda, e a revisão do diff do arquivo
// `.snap` versionado é quem decide se a divergência é intencional. O que
// continua pegando regressão é uma mudança inesperada dentro da MESMA
// plataforma entre execuções.
jest.mock('react-native/Libraries/Utilities/Platform', () => {
  // Não usar spread: o objeto real expõe `constants`/`Version`/etc. como
  // getters que acionam módulos nativos (indisponíveis em teste) assim que
  // lidos. Sobrescrevemos só `OS`, preservando os getters intocados.
  const actual = jest.requireActual('react-native/Libraries/Utilities/Platform');
  Object.defineProperty(actual, 'OS', { value: 'ios', writable: true, configurable: true });
  return actual;
});

jest.mock('../../api/endpoints', () => ({
  recordsApi: {
    create: jest.fn(() => Promise.resolve({ data: {} })),
    update: jest.fn(() => Promise.resolve({ data: {} })),
  },
  medicationsApi: {
    list: jest.fn(() => Promise.resolve({ data: { results: [] } })),
  },
}));

jest.mock('@react-native-async-storage/async-storage', () => ({
  getItem: jest.fn(() => Promise.resolve(null)),
  setItem: jest.fn(() => Promise.resolve()),
  removeItem: jest.fn(() => Promise.resolve()),
}));

const mockGoBack = jest.fn();
jest.mock('@react-navigation/native', () => ({
  useNavigation: () => ({ goBack: mockGoBack }),
  useRoute: () => ({ params: {} }),
}));

jest.mock('../../components/DateTimePicker', () => {
  const { View, Text } = require('react-native');
  return function MockDateTimePicker({ label }: { label: string }) {
    return (
      <View>
        <Text>{label}</Text>
      </View>
    );
  };
});

// Localiza o TouchableOpacity mais próximo que contém o texto informado,
// percorrendo a árvore de fibers (não o toJSON()), para poder inspecionar
// seu `style` resolvido independentemente de como o serializer de snapshot
// achataria a prop.
function findTouchableByText(root: ReturnType<typeof render>, text: string): ReturnType<typeof root.UNSAFE_getAllByType>[number] {
  const candidates = root.UNSAFE_getAllByType(TouchableOpacity);
  const match = candidates.find((node) => {
    try {
      within(node).getByText(text);
      return true;
    } catch {
      return false;
    }
  });
  if (!match) {
    throw new Error(`TouchableOpacity contendo o texto "${text}" não foi encontrado.`);
  }
  return match;
}

describe.each(['ios', 'web'] as const)(
  'RecordCreateScreen - fluxo Adicionar remédio sob Platform.OS = %s',
  (os) => {
    beforeEach(() => {
      jest.clearAllMocks();
      (medicationsApi.list as jest.Mock).mockResolvedValue({ data: { results: [] } });

      // Muta a mesma instância mockada do módulo Platform para simular a
      // plataforma alvo desta rodada, sem precisar de jest.resetModules()
      // (que quebraria o registro global de hooks do testing-library).
      const Platform = require('react-native/Libraries/Utilities/Platform');
      Platform.OS = os;
    });

    it(`renderiza o formulário de medicamento sem crashar (${os})`, async () => {
      const root = render(<RecordCreateScreen />);
      const { getByText, findByText } = root;

      fireEvent.press(getByText('Remédio'));

      await findByText('Outro', {}, { timeout: 3000 });

      expect(() => root.toJSON()).not.toThrow();
      expect(recordsApi.create).not.toHaveBeenCalled();
    }, 15000);

    it(`snapshot dos estilos do design system no formulário de medicamento (${os})`, async () => {
      const root = render(<RecordCreateScreen />);
      const { getByText, findByText, findByPlaceholderText } = root;

      fireEvent.press(getByText('Remédio'));
      await findByText('Outro', {}, { timeout: 3000 });

      // Seleciona "Outro" para revelar o FormField de texto livre e colocar
      // o botão de opção em estado "ativo".
      fireEvent.press(getByText('Outro'));

      const optionButton = findTouchableByText(root, 'Outro');
      const optionStyle = StyleSheet.flatten(optionButton.props.style);
      // pickerOption + pickerOptionActive (RecordCreateScreen.tsx).
      expect(optionStyle).toMatchSnapshot(`pickerOption ativo (${os})`);

      const otherMedicationInput = await findByPlaceholderText('Nome e dose', {}, { timeout: 3000 });
      const inputStyle = StyleSheet.flatten(otherMedicationInput.props.style);
      // Estilo do FormField (frontend/src/components/FormField.tsx) — um
      // Platform.OS específico ausente quebraria isso silenciosamente em
      // Web sem lançar exceção nenhuma, por isso registramos o valor
      // concreto via snapshot em vez de só checar "não quebrou".
      expect(inputStyle).toMatchSnapshot(`FormField "Nome e dose" (${os})`);

      const quantityInput = await findByPlaceholderText('1', {}, { timeout: 3000 });
      const quantityStyle = StyleSheet.flatten(quantityInput.props.style);
      expect(quantityStyle).toMatchSnapshot(`FormField quantidade (${os})`);

      const submitButton = findTouchableByText(root, 'Salvar');
      const submitStyle = StyleSheet.flatten(submitButton.props.style);
      // Estilo do botão de submit — verifica que o botão não fica sem
      // altura mínima/cor em nenhuma plataforma (regressão clássica de
      // Web quando `minHeight` numérico depende de resolução de unidade
      // específica de plataforma).
      expect(submitStyle).toMatchSnapshot(`botão Salvar (${os})`);

      expect(recordsApi.create).not.toHaveBeenCalled();
    }, 15000);
  }
);
