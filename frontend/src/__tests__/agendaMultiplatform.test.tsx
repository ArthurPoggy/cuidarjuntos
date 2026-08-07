import React from 'react';
import { Platform } from 'react-native';
import { NavigationContainer } from '@react-navigation/native';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import { render, waitFor, cleanup, act } from '@testing-library/react-native';
import { renderHook } from '@testing-library/react-native';

import UpcomingScreen from '../screens/UpcomingScreen';
import { useCalendarNavigation } from '../hooks/useCalendarNavigation';
import { dashboardApi, recordsApi } from '../api/endpoints';

/**
 * Teste para a tarefa #110 "Consertar agenda -> MOBILE", item "Validar
 * renderizacao multiplataforma (iOS/Android) e ausencia de erros
 * TypeScript em todo o codigo alterado da agenda".
 *
 * Cobre, com `Platform.OS` mockado para 'ios' e depois para 'android', que
 * todo o conjunto de arquivos tocados pelas subtasks anteriores da tarefa
 * #110 -- UpcomingScreen (frontend/src/screens/UpcomingScreen.tsx),
 * utilitario de datas (frontend/src/utils/date.ts, usado indiretamente via
 * `formatAgendaDayLabel` dentro de UpcomingScreen), utilitario de navegacao
 * de calendario (frontend/src/utils/calendarNavigation.ts) e o hook
 * frontend/src/hooks/useCalendarNavigation.ts -- renderiza/monta sem lancar
 * excecao em nenhuma das duas plataformas.
 *
 * A parte de "zero erros TypeScript" (`npx tsc --noEmit` com exit code 0)
 * ja e coberta por src/__tests__/typecheck.test.ts (script `typecheck` do
 * package.json, exigido pela subtask de infraestrutura de testes); este
 * arquivo cobre a parte de renderizacao multiplataforma exigida pelo mesmo
 * item de aceitacao.
 */

jest.mock('@react-native-async-storage/async-storage', () =>
  require('@react-native-async-storage/async-storage/jest/async-storage-mock')
);

jest.mock('../api/endpoints', () => ({
  dashboardApi: {
    upcomingBuckets: jest.fn(),
    calendar: jest.fn(),
  },
  recordsApi: {
    bulkSetStatus: jest.fn(),
  },
}));

const mockedUpcomingBuckets = dashboardApi.upcomingBuckets as jest.Mock;
const mockedCalendar = dashboardApi.calendar as jest.Mock;

const Stack = createNativeStackNavigator();

async function renderUpcomingScreen() {
  return render(
    <NavigationContainer>
      <Stack.Navigator>
        <Stack.Screen name="Upcoming" component={UpcomingScreen} />
      </Stack.Navigator>
    </NavigationContainer>
  );
}

const SAMPLE_BUCKETS = [
  {
    date_iso: '2026-08-10',
    items: [
      {
        id: 1,
        type: 'medication',
        title: 'Remedio X',
        time: '08:00',
        who: 'Cuidador',
        status: 'pending',
        series: false,
      },
    ],
  },
];

describe.each(['ios', 'android'] as const)(
  'Renderizacao multiplataforma da agenda (Platform.OS = %s)',
  (platformOs) => {
    const originalOS = Platform.OS;

    beforeEach(() => {
      jest.clearAllMocks();
      Platform.OS = platformOs;
      mockedUpcomingBuckets.mockResolvedValue({ data: { buckets: SAMPLE_BUCKETS, totals: {} } });
      mockedCalendar.mockResolvedValue({
        data: {
          year: 2026,
          month: 8,
          month_name: 'Agosto',
          weeks: [],
          days_with: [],
          today_iso: '2026-08-06',
          events_by_date: {},
        },
      });
    });

    afterEach(() => {
      cleanup();
      Platform.OS = originalOS;
    });

    it('UpcomingScreen monta e carrega a lista de agenda sem lancar excecao', async () => {
      let screen: Awaited<ReturnType<typeof renderUpcomingScreen>> | undefined;

      await expect(
        (async () => {
          screen = await renderUpcomingScreen();
        })()
      ).resolves.not.toThrow();

      await waitFor(() => expect(mockedUpcomingBuckets).toHaveBeenCalled());
      expect(await screen!.findByText('Remedio X')).toBeTruthy();
    });

    it('useCalendarNavigation monta e busca o mes atual sem lancar excecao', async () => {
      let hookResult: { result: { current: ReturnType<typeof useCalendarNavigation> } } | undefined;

      await expect(
        (async () => {
          hookResult = await renderHook(() => useCalendarNavigation());
        })()
      ).resolves.not.toThrow();

      await waitFor(() => expect(mockedCalendar).toHaveBeenCalledTimes(1));
      await waitFor(() => expect(hookResult!.result.current.loading).toBe(false));
      expect(hookResult!.result.current.calendarData).not.toBeNull();

      await act(async () => {
        hookResult!.result.current.goToNextMonth();
      });
      await waitFor(() => expect(mockedCalendar).toHaveBeenCalledTimes(2));
    });
  }
);
