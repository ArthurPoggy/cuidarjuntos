import React from 'react';
import { render, fireEvent, waitFor } from '@testing-library/react-native';
import RecordCreateScreen from '../RecordCreateScreen';

jest.mock('../../contexts/AuthContext', () => ({
  useAuth: () => ({
    tokens: { access: 'fake-access-token', refresh: 'fake-refresh-token' },
  }),
}));
import { recordsApi, medicationsApi, integrationsApi } from '../../api/endpoints';

jest.mock('../../api/endpoints', () => ({
  recordsApi: {
    create: jest.fn(() => Promise.resolve({ data: {} })),
    update: jest.fn(() => Promise.resolve({ data: {} })),
  },
  medicationsApi: {
    list: jest.fn(() => Promise.resolve({ data: { results: [] } })),
  },
  integrationsApi: {
    calendarStatus: jest.fn(),
  },
}));

jest.mock('@react-native-async-storage/async-storage', () => ({
  getItem: jest.fn(() => Promise.resolve(null)),
  setItem: jest.fn(() => Promise.resolve()),
  removeItem: jest.fn(() => Promise.resolve()),
}));

const mockGoBack = jest.fn();
let mockRouteParams: Record<string, unknown> = {};
jest.mock('@react-navigation/native', () => ({
  useNavigation: () => ({ goBack: mockGoBack }),
  useRoute: () => ({ params: mockRouteParams }),
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

const connected = (providers: string[]) => ({
  data: { connected: providers.length > 0, providers },
});

/** Preenche o mínimo para chegar ao submit na categoria "Sono". */
async function goToFormAndSubmit(utils: any) {
  const { getByText, findByText } = utils;
  await fireEvent.press(getByText('Sono'));
  const submitButton = await findByText('Salvar', {}, { timeout: 3000 });
  await fireEvent.press(submitButton);
}

describe('RecordCreateScreen - sincronizacao com calendario externo (#41)', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockRouteParams = {};
    (medicationsApi.list as jest.Mock).mockResolvedValue({
      data: { results: [] },
    });
  });

  it('nao mostra o controle quando nao ha integracao conectada', async () => {
    (integrationsApi.calendarStatus as jest.Mock).mockResolvedValue(
      connected([])
    );

    const utils = await render(<RecordCreateScreen />);
    await fireEvent.press(utils.getByText('Sono'));

    await waitFor(() => {
      expect(integrationsApi.calendarStatus).toHaveBeenCalled();
    });
    expect(utils.queryByTestId('sync-to-calendar-switch')).toBeNull();
  }, 15000);

  it('mostra o controle e nomeia o provedor quando ha um conectado', async () => {
    (integrationsApi.calendarStatus as jest.Mock).mockResolvedValue(
      connected(['google'])
    );

    const utils = await render(<RecordCreateScreen />);
    await fireEvent.press(utils.getByText('Sono'));

    const toggle = await utils.findByTestId(
      'sync-to-calendar-switch',
      {},
      { timeout: 3000 }
    );
    expect(toggle).toBeTruthy();
    expect(utils.queryByText(/Google Agenda/i)).toBeTruthy();
  }, 15000);

  it('envia sync_to_calendar=true quando o usuario liga o controle', async () => {
    (integrationsApi.calendarStatus as jest.Mock).mockResolvedValue(
      connected(['google'])
    );

    const utils = await render(<RecordCreateScreen />);
    await fireEvent.press(utils.getByText('Sono'));

    const toggle = await utils.findByTestId(
      'sync-to-calendar-switch',
      {},
      { timeout: 3000 }
    );
    await fireEvent(toggle, 'valueChange', true);

    const submitButton = await utils.findByText('Salvar', {}, { timeout: 3000 });
    await fireEvent.press(submitButton);

    await waitFor(() => {
      expect(recordsApi.create).toHaveBeenCalled();
    });
    const payload = (recordsApi.create as jest.Mock).mock.calls[0][0];
    expect(payload.sync_to_calendar).toBe(true);
  }, 15000);

  it('envia false quando sabidamente nao ha integracao conectada', async () => {
    (integrationsApi.calendarStatus as jest.Mock).mockResolvedValue(
      connected([])
    );

    const utils = await render(<RecordCreateScreen />);
    await goToFormAndSubmit(utils);

    await waitFor(() => {
      expect(recordsApi.create).toHaveBeenCalled();
    });
    const payload = (recordsApi.create as jest.Mock).mock.calls[0][0];
    expect(payload.sync_to_calendar).toBe(false);
  }, 15000);

  it('preserva o sync_to_calendar do registro quando o status falha', async () => {
    // Regressao: com o status indisponivel, editar um registro ja marcado
    // desligava a sincronizacao silenciosamente -- o controle nem chegava a
    // ser renderizado, entao o usuario nao tinha como perceber.
    (integrationsApi.calendarStatus as jest.Mock).mockRejectedValue(
      new Error('rede instavel')
    );
    mockRouteParams = {
      record: {
        id: 7,
        type: 'sleep',
        what: 'Dormiu',
        description: '',
        date: '2026-08-28',
        time: '22:00',
        sync_to_calendar: true,
        is_exception: false,
        recurrence: 'none',
        repeat_until: null,
      },
    };

    const utils = await render(<RecordCreateScreen />);
    const submitButton = await utils.findByText(
      'Atualizar',
      {},
      { timeout: 3000 }
    );
    await fireEvent.press(submitButton);

    await waitFor(() => {
      expect(recordsApi.update).toHaveBeenCalled();
    });
    const payload = (recordsApi.update as jest.Mock).mock.calls[0][1];
    expect(payload.sync_to_calendar).toBe(true);
  }, 15000);
});
