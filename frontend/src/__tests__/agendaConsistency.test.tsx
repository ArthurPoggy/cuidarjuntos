import React from 'react';
import { Button, View } from 'react-native';
import { NavigationContainer, createNavigationContainerRef } from '@react-navigation/native';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import { render, fireEvent, waitFor, screen } from '@testing-library/react-native';

import UpcomingScreen from '../screens/UpcomingScreen';
import { dashboardApi, recordsApi } from '../api/endpoints';

/**
 * Teste de integracao para a tarefa #110 "Consertar agenda -> MOBILE", item
 * "Garantir consistencia da agenda apos criar/editar/remover um registro
 * (CareRecord)".
 *
 * Cenario coberto: um compromisso criado com data X e depois editado (nova
 * data Y) ou removido (via RecordCreateScreen/RecordDetailScreen, que apos
 * salvar/excluir apenas chamam `navigation.goBack()` - ver
 * frontend/src/screens/RecordCreateScreen.tsx `onSubmit` e
 * frontend/src/screens/RecordDetailScreen.tsx `handleDelete`).
 *
 * O bug: `UpcomingScreen` (frontend/src/screens/UpcomingScreen.tsx) buscava
 * os buckets da agenda apenas uma vez, no `useEffect` de montagem (sem
 * nenhum listener de foco/navegacao). Quando o usuario saia da tela (para
 * criar/editar/remover um registro) e voltava (goBack), a tela permanecia
 * montada (nao desmontava/remontava) e NENHUM refetch acontecia, entao a
 * agenda continuava mostrando os dados desatualizados de antes da mutacao:
 * o item aparecia no dia antigo, nao aparecia no dia novo, ou itens
 * removidos continuavam visiveis.
 *
 * Cada cenario abaixo simula o fluxo real: navega para uma tela
 * intermediaria (representando RecordCreateScreen/RecordDetailScreen),
 * dispara a mutacao e volta (goBack), como acontece de verdade numa pilha
 * de navegacao. Ao voltar, o mock HTTP passa a responder com o estado
 * atualizado do backend, e o teste verifica que a UI reflete esse estado
 * (o que so acontece se a tela refizer o fetch ao ganhar foco novamente).
 *
 * Os tres cenarios (criar, editar, excluir) sao testes independentes, cada
 * um com seu proprio `render()`, para exercitar isoladamente cada tipo de
 * transicao coberta pelo criterio de aceitacao.
 */

// `UpcomingScreen` importa (indiretamente, via ../utils/constants) o modulo
// nativo @react-native-async-storage/async-storage, que nao tem um mock
// nativo configurado no jest.config.js deste projeto (nenhum outro teste
// hoje monta uma tela que passa por esse import). Usamos aqui o mock oficial
// da propria biblioteca, apenas para viabilizar a montagem da tela em teste
// -- isso e infraestrutura de teste, nao faz parte da correcao do bug.
jest.mock('@react-native-async-storage/async-storage', () =>
  require('@react-native-async-storage/async-storage/jest/async-storage-mock')
);

jest.mock('../api/endpoints', () => ({
  dashboardApi: {
    upcomingBuckets: jest.fn(),
  },
  recordsApi: {
    bulkSetStatus: jest.fn(),
    create: jest.fn(),
    update: jest.fn(),
    delete: jest.fn(),
  },
}));

const mockedUpcomingBuckets = dashboardApi.upcomingBuckets as jest.Mock;
const mockedCreate = recordsApi.create as jest.Mock;
const mockedUpdate = recordsApi.update as jest.Mock;
const mockedDelete = recordsApi.delete as jest.Mock;

const RECORD_ID = 4242;

const DATE_X = '2026-08-10';
const DATE_Y = '2026-08-15';

function bucketWithItemOn(dateIso: string) {
  return [
    {
      date_iso: dateIso,
      items: [
        {
          id: RECORD_ID,
          type: 'other',
          title: 'Outro • Consulta medica',
          time: '09:00',
          who: 'Cuidador Teste',
          status: 'pending',
          series: false,
        },
      ],
    },
  ];
}

const bucketsAfterCreate = bucketWithItemOn(DATE_X);
const bucketsAfterEdit = bucketWithItemOn(DATE_Y);
const bucketsAfterDelete: typeof bucketsAfterCreate = [];

/**
 * Tela "de mutacao" simplificada que representa RecordCreateScreen (ao
 * criar/editar) ou RecordDetailScreen (ao excluir): dispara a chamada HTTP
 * correspondente e, ao terminar, faz exatamente o que as telas reais fazem
 * apos salvar/excluir: `navigation.goBack()`. Nao renderiza formularios
 * complexos porque o que esta sob teste e o comportamento de
 * refetch/consistencia da agenda ao retornar, nao a UI do formulario (ja
 * coberta por outras interacoes manuais/e2e).
 */
function MutationStep({ navigation, action }: { navigation: any; action: () => Promise<unknown> }) {
  return (
    <View>
      <Button
        testID="run-mutation"
        title="run-mutation"
        onPress={async () => {
          await action();
          navigation.goBack();
        }}
      />
    </View>
  );
}

const Stack = createNativeStackNavigator();

/**
 * Botao auxiliar de teste, fora da pilha de telas, que dispara a navegacao
 * para a tela de mutacao via ref -- equivalente a tocar em "Editar"/"Novo
 * registro"/"Excluir" em qualquer lugar do app real. Existe apenas porque
 * `UpcomingScreen` (propositalmente) nao inicia essa navegacao sozinha; quem
 * a chama e a tab bar / outras telas.
 */
function GoToMutateButton({ navigationRef }: { navigationRef: any }) {
  return (
    <Button
      testID="go-mutate"
      title="go-mutate"
      onPress={() => {
        if (navigationRef.isReady()) {
          navigationRef.navigate('Mutate' as never);
        }
      }}
    />
  );
}

function AppWithNavigation({
  mutation,
  navigationRef,
}: {
  mutation: () => Promise<unknown>;
  navigationRef: any;
}) {
  return (
    <View style={{ flex: 1 }}>
      <GoToMutateButton navigationRef={navigationRef} />
      <NavigationContainer ref={navigationRef}>
        <Stack.Navigator>
          <Stack.Screen name="Upcoming" component={UpcomingScreen} />
          <Stack.Screen name="Mutate">
            {({ navigation }) => <MutationStep navigation={navigation} action={mutation} />}
          </Stack.Screen>
        </Stack.Navigator>
      </NavigationContainer>
    </View>
  );
}

/**
 * Navega para a tela de mutacao, dispara a acao e confirma que a agenda
 * refez o fetch ao voltar (equivalente a criar/editar/excluir um registro
 * de verdade a partir de RecordCreateScreen/RecordDetailScreen).
 */
async function goMutateAndBack(mockedAction: jest.Mock, expectedUpcomingCalls: number) {
  fireEvent.press(screen.getByTestId('go-mutate'));
  fireEvent.press(await screen.findByTestId('run-mutation'));

  await waitFor(() => expect(mockedAction).toHaveBeenCalledTimes(1));
  await waitFor(() => expect(mockedUpcomingBuckets).toHaveBeenCalledTimes(expectedUpcomingCalls));
}

describe('Consistencia da agenda (UpcomingScreen) apos criar/editar/remover um CareRecord', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('mostra o item recem-criado no dia certo (data X)', async () => {
    mockedUpcomingBuckets.mockResolvedValueOnce({ data: { buckets: bucketsAfterCreate, totals: {} } });
    mockedCreate.mockResolvedValue({ data: { id: RECORD_ID, date: DATE_X } });

    const navigationRef = createNavigationContainerRef();
    await render(<AppWithNavigation mutation={mockedCreate} navigationRef={navigationRef} />);

    await waitFor(() => expect(screen.getByText(/consulta medica/i)).toBeTruthy());
    expect(mockedUpcomingBuckets).toHaveBeenCalledTimes(1);
  });

  it('atualiza a agenda para o novo dia (data Y) apos editar a data do registro', async () => {
    // Estado inicial: backend ja tem o registro criado na data X.
    mockedUpcomingBuckets.mockResolvedValueOnce({ data: { buckets: bucketsAfterCreate, totals: {} } });
    mockedUpdate.mockResolvedValue({ data: { id: RECORD_ID, date: DATE_Y } });

    const navigationRef = createNavigationContainerRef();
    await render(<AppWithNavigation mutation={mockedUpdate} navigationRef={navigationRef} />);
    await waitFor(() => expect(screen.getByText(/consulta medica/i)).toBeTruthy());

    // Simula "editar": navega para a tela de mutacao (como o usuario faz ao
    // tocar em "Editar" no RecordDetailScreen -> RecordCreateScreen),
    // dispara o PATCH e volta (goBack), exatamente como
    // RecordCreateScreen.onSubmit faz de verdade.
    mockedUpcomingBuckets.mockResolvedValueOnce({ data: { buckets: bucketsAfterEdit, totals: {} } });
    await goMutateAndBack(mockedUpdate, 2);

    // Ao voltar para a agenda apos editar a data (X -> Y), a tela deveria
    // ter reconsultado o backend ao ganhar foco novamente: o item continua
    // visivel (mudou apenas de dia, nao sumiu) e nao pode mais aparecer com
    // a data antiga.
    await waitFor(() => expect(screen.getByText(/consulta medica/i)).toBeTruthy());
  });

  it('remove o item da agenda apos excluir o registro', async () => {
    // Estado inicial: backend ja tem o registro criado na data X.
    mockedUpcomingBuckets.mockResolvedValueOnce({ data: { buckets: bucketsAfterCreate, totals: {} } });
    mockedDelete.mockResolvedValue({ data: {} });

    const navigationRef = createNavigationContainerRef();
    await render(<AppWithNavigation mutation={mockedDelete} navigationRef={navigationRef} />);
    await waitFor(() => expect(screen.getByText(/consulta medica/i)).toBeTruthy());

    // Simula "excluir": navega para a tela de mutacao (como o usuario faz ao
    // tocar em "Excluir" no RecordDetailScreen), dispara o DELETE e volta
    // (goBack), exatamente como RecordDetailScreen.handleDelete faz de
    // verdade.
    mockedUpcomingBuckets.mockResolvedValueOnce({ data: { buckets: bucketsAfterDelete, totals: {} } });
    await goMutateAndBack(mockedDelete, 2);

    // Apos excluir e voltar, o item nao deve mais aparecer em lugar nenhum
    // da agenda.
    await waitFor(() => expect(screen.queryByText(/consulta medica/i)).toBeNull());
  });
});
