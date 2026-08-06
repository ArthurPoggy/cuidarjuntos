import React from 'react';
import { View } from 'react-native';
import { NavigationContainer } from '@react-navigation/native';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import { render, fireEvent } from '@testing-library/react-native';
import Header from '../Header';

/**
 * Testes automatizados exigidos pela tarefa #107 "Ajeitar menu de
 * hamburguer -> MOBILE", item "Destacar o item de navegação ativo no menu".
 *
 * Diferente de uma versão anterior deste arquivo, aqui @react-navigation/native
 * NÃO é mockado. Header é renderizado exatamente como acontece em produção
 * (ver frontend/src/navigation/RootNavigator.tsx -> MainNavigator): como o
 * `header` de um `createNativeStackNavigator`, dentro de um NavigationContainer
 * real, com Screens reais para cada rota do menu, recebendo `activeRouteName`
 * a partir do `route` injetado pelo próprio Navigator (mesma forma como
 * MainNavigator monta o Header). Isso é proposital: uma implementação que só
 * funciona com o estado de navegação mockado (e quebra quando o Header roda
 * dentro do navigator real de produção, ou dentro do <NavigationContainer>
 * "nu" usado por Header.test.tsx, onde nenhuma prop é passada) precisa ser
 * pega por este arquivo, não escondida por ele.
 *
 * Critério de aceitação coberto:
 *  Renderiza <Header /> com a rota ativa real do navigator (via
 *  initialRouteName), abre o menu, e verifica que apenas o TouchableOpacity
 *  correspondente ao item ativo tem `accessibilityState.selected === true`,
 *  enquanto os demais itens não têm. Cobre as 8 rotas citadas no card:
 *  Dashboard, RecordCreate, Records, Medications, Upcoming, Chat,
 *  Notifications e Profile.
 */

jest.mock('../../contexts/AuthContext', () => ({
  useAuth: () => ({
    user: { id: 1, username: 'demo' },
    group: null,
    isAuthenticated: true,
    hasGroup: false,
    logout: jest.fn(),
  }),
}));

// chatAvailable = true para que o item "Assistente" (rota Chat) seja
// renderizado no menu e possa ser verificado como os demais.
jest.mock('../../hooks/useChat', () => ({
  useChatAvailable: () => ({ data: true }),
}));

jest.mock('../../hooks/useUnreadNotifications', () => ({
  useUnreadNotifications: () => ({ count: 0, refresh: jest.fn() }),
}));

const Stack = createNativeStackNavigator();

// Telas fake mínimas só para existir algo para o navigator montar; o que
// importa para o teste é o `header: () => <Header />`, igual ao
// MainNavigator real.
function DummyScreen() {
  return <View />;
}

// Mesmas rotas registradas em MainNavigator (RootNavigator.tsx), na mesma
// ordem em que o card #107 as cita: Dashboard, RecordCreate, Records,
// Medications, Upcoming, Chat, Notifications, Profile.
const ROUTES = [
  'Dashboard',
  'RecordCreate',
  'Records',
  'Medications',
  'Upcoming',
  'Chat',
  'Notifications',
  'Profile',
] as const;

// Mapa rota -> label do item de menu correspondente, conforme os `onPress`
// de Header.tsx.
const ROUTE_TO_LABEL: Record<(typeof ROUTES)[number], string> = {
  Dashboard: '🏠  Dashboard',
  RecordCreate: '➕  Novo Registro',
  Records: '📋  Registros',
  Medications: '💊  Remédios',
  Upcoming: '📅  Agenda',
  Chat: '🤖  Assistente',
  Notifications: '🔔  Notificações',
  Profile: '👤  Perfil',
};

/**
 * Dado o texto (label) de um item do menu, retorna a instância do
 * TouchableOpacity ancestral (identificado por possuir `onPress` nas
 * props ou `accessibilityState`), para inspecionar `accessibilityState`.
 */
function findTouchableAncestor(instance: any): any {
  let node = instance;
  while (node) {
    if (
      node.props &&
      (typeof node.props.onPress === 'function' || node.props.accessibilityState)
    ) {
      return node;
    }
    node = node.parent;
  }
  return null;
}

function isSelected(touchable: any): boolean {
  return touchable?.props?.accessibilityState?.selected === true;
}

async function renderHeaderOnRoute(activeRoute: (typeof ROUTES)[number]) {
  const { getByTestId, getByText } = await render(
    <NavigationContainer>
      <Stack.Navigator
        initialRouteName={activeRoute}
        screenOptions={{ header: ({ route }) => <Header activeRouteName={route.name} /> }}
      >
        {ROUTES.map((name) => (
          <Stack.Screen key={name} name={name} component={DummyScreen} />
        ))}
      </Stack.Navigator>
    </NavigationContainer>
  );

  await fireEvent.press(getByTestId('header-menu-button'));

  return { getByTestId, getByText };
}

describe('Header - item de navegação ativo destacado no menu', () => {
  it.each(ROUTES)(
    "destaca apenas o item correspondente à rota ativa '%s', e nenhum outro",
    async (activeRoute) => {
      const { getByText } = await renderHeaderOnRoute(activeRoute);

      for (const route of ROUTES) {
        const label = ROUTE_TO_LABEL[route];
        const textNode = getByText(label);
        const touchable = findTouchableAncestor(textNode);
        expect(touchable).toBeTruthy();

        if (route === activeRoute) {
          expect(isSelected(touchable)).toBe(true);
        } else {
          expect(isSelected(touchable)).toBe(false);
        }
      }
    }
  );

  it("muda o destaque de 'Dashboard' para 'Records' quando a rota ativa muda", async () => {
    const onDashboard = await renderHeaderOnRoute('Dashboard');
    const dashboardTouchable = findTouchableAncestor(
      onDashboard.getByText(ROUTE_TO_LABEL.Dashboard)
    );
    const recordsTouchableWhileOnDashboard = findTouchableAncestor(
      onDashboard.getByText(ROUTE_TO_LABEL.Records)
    );
    expect(isSelected(dashboardTouchable)).toBe(true);
    expect(isSelected(recordsTouchableWhileOnDashboard)).toBe(false);

    const onRecords = await renderHeaderOnRoute('Records');
    const dashboardTouchableWhileOnRecords = findTouchableAncestor(
      onRecords.getByText(ROUTE_TO_LABEL.Dashboard)
    );
    const recordsTouchable = findTouchableAncestor(
      onRecords.getByText(ROUTE_TO_LABEL.Records)
    );
    expect(isSelected(dashboardTouchableWhileOnRecords)).toBe(false);
    expect(isSelected(recordsTouchable)).toBe(true);
  });
});
