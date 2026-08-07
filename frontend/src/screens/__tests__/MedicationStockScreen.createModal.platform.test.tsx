import React from 'react';
import { StyleSheet, TouchableOpacity } from 'react-native';
import { render, fireEvent, within } from '@testing-library/react-native';
import MedicationStockScreen from '../MedicationStockScreen';
import { medicationsApi } from '../../api/endpoints';

// Tarefa #99 (subtask 4): garante que o modal "Cadastrar novo remédio"
// (MedicationStockScreen) renderiza sem quebrar tanto em Platform.OS =
// 'ios' quanto em Platform.OS = 'web' (react-native-web), já que o app
// roda nas duas plataformas via Expo, e que os estilos aplicados aos
// campos e botões do modal ficam registrados via `toMatchSnapshot()` — a
// técnica pedida literalmente pelo AC da subtask 4 ("snapshot tests ... os
// snapshots batem") — em vez de apenas comparar os textos visíveis (o que
// não detectaria estilo hardcoded/quebrado) ou de reafirmar via
// `toMatchObject` um objeto fixo que teria de ser idêntico nas duas
// plataformas.
//
// Cada plataforma grava seu próprio snapshot nomeado (o hint passado a
// `toMatchSnapshot` já inclui, via describe.each, qual Platform.OS gerou o
// valor). Isso é deliberado: se um dia uma ramificação Platform.OS legítima
// e correta passar a existir em MedicationStockScreen/FormField/PrimaryButton/
// SecondaryButton e produzir um valor diferente por plataforma, o teste não
// falha por definição (como falharia comparando ambas contra o mesmo objeto
// esperado) — o snapshot daquela plataforma específica só muda, e a revisão
// do diff do arquivo `.snap` versionado é quem decide se a divergência é
// intencional. O que continua pegando regressão é uma mudança inesperada
// dentro da MESMA plataforma entre execuções.
jest.mock('react-native/Libraries/Utilities/Platform', () => {
  // Não usar spread: o objeto real expõe `constants`/`Version`/etc. como
  // getters que acionam módulos nativos (indisponíveis em teste) assim que
  // lidos. Sobrescrevemos só `OS`, preservando os getters intocados.
  const actual = jest.requireActual('react-native/Libraries/Utilities/Platform');
  Object.defineProperty(actual, 'OS', { value: 'ios', writable: true, configurable: true });
  return actual;
});

jest.mock('../../api/endpoints', () => ({
  medicationsApi: {
    stockOverview: jest.fn(() => Promise.resolve({ data: { sections: [] } })),
    create: jest.fn(() => Promise.resolve({ data: { id: 1, name: 'Paracetamol', dosage: '500mg' } })),
    addStock: jest.fn(() => Promise.resolve({ data: {} })),
  },
}));

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
  'MedicationStockScreen - modal Novo Medicamento sob Platform.OS = %s',
  (os) => {
    beforeEach(() => {
      jest.clearAllMocks();
      (medicationsApi.stockOverview as jest.Mock).mockResolvedValue({ data: { sections: [] } });

      // Muta a mesma instância mockada do módulo Platform para simular a
      // plataforma alvo desta rodada, sem precisar de jest.resetModules()
      // (que quebraria o registro global de hooks do testing-library).
      const Platform = require('react-native/Libraries/Utilities/Platform');
      Platform.OS = os;
    });

    it(`renderiza o modal de novo medicamento sem crashar (${os})`, async () => {
      const root = render(<MedicationStockScreen />);
      const { getByText, findByText } = root;

      await findByText('+ Novo', {}, { timeout: 3000 });
      fireEvent.press(getByText('+ Novo'));

      await findByText('Novo Medicamento', {}, { timeout: 3000 });

      expect(() => root.toJSON()).not.toThrow();
      expect(medicationsApi.create).not.toHaveBeenCalled();
    }, 15000);

    it(`snapshot dos estilos do design system no modal de novo medicamento (${os})`, async () => {
      const root = render(<MedicationStockScreen />);
      const { getByText, findByText, findByPlaceholderText } = root;

      await findByText('+ Novo', {}, { timeout: 3000 });
      fireEvent.press(getByText('+ Novo'));
      await findByText('Novo Medicamento', {}, { timeout: 3000 });

      const nameInput = await findByPlaceholderText('Ex: Paracetamol', {}, { timeout: 3000 });
      const nameStyle = StyleSheet.flatten(nameInput.props.style);
      // Estilo do FormField (frontend/src/components/FormField.tsx) — um
      // Platform.OS específico ausente quebraria isso silenciosamente em
      // Web sem lançar exceção nenhuma, por isso registramos o valor
      // concreto via snapshot em vez de só checar "não quebrou".
      expect(nameStyle).toMatchSnapshot(`FormField "Ex: Paracetamol" (${os})`);

      const dosageInput = await findByPlaceholderText('Ex: 500mg', {}, { timeout: 3000 });
      const dosageStyle = StyleSheet.flatten(dosageInput.props.style);
      expect(dosageStyle).toMatchSnapshot(`FormField "Ex: 500mg" (${os})`);

      const cancelButton = findTouchableByText(root, 'Cancelar');
      const cancelStyle = StyleSheet.flatten(cancelButton.props.style);
      // Estilo do SecondaryButton (frontend/src/components/SecondaryButton.tsx)
      // com o override de layout do modal (styles.modalActionBtn em
      // MedicationStockScreen.tsx, aplicado por cima via prop `style`).
      expect(cancelStyle).toMatchSnapshot(`botão Cancelar (${os})`);

      const createButton = findTouchableByText(root, 'Criar');
      const createStyle = StyleSheet.flatten(createButton.props.style);
      // Estilo do PrimaryButton (frontend/src/components/PrimaryButton.tsx)
      // com o override de layout do modal (styles.modalActionBtn) — verifica
      // que o botão de ação principal do modal não fica sem altura
      // mínima/cor em nenhuma plataforma.
      expect(createStyle).toMatchSnapshot(`botão Criar (${os})`);

      expect(medicationsApi.create).not.toHaveBeenCalled();
    }, 15000);
  }
);
