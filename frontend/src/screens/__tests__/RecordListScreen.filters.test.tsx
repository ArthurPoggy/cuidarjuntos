import React from 'react';
import { render, fireEvent, waitFor } from '@testing-library/react-native';
import RecordListScreen from '../RecordListScreen';
import { recordsApi } from '../../api/endpoints';

/**
 * Card #102 "Adicionar filtros no historico de registros": cobre filtros
 * combinaveis (tipo, intervalo de datas, autor), opcao de limpar filtros,
 * atualizacao imediata da lista e indicacao visual de filtros ativos.
 */

jest.mock('../../api/endpoints', () => ({
  recordsApi: {
    list: jest.fn(),
    authors: jest.fn(),
  },
}));

jest.mock('@react-navigation/native', () => ({
  useNavigation: () => ({ navigate: jest.fn() }),
  useRoute: () => ({ params: {} }),
}));

jest.mock('../../components/DateTimePicker', () => {
  const { View, Text, TouchableOpacity } = require('react-native');
  return function MockDateTimePicker({
    label,
    onChange,
  }: {
    label: string;
    onChange: (date: Date) => void;
  }) {
    return (
      <View>
        <Text>{label}</Text>
        <TouchableOpacity onPress={() => onChange(new Date('2026-01-08T00:00:00'))}>
          <Text>{`selecionar-${label}`}</Text>
        </TouchableOpacity>
      </View>
    );
  };
});

const mockRecord = (overrides: Record<string, unknown> = {}) => ({
  id: 1,
  patient: 1,
  type: 'medication',
  what: 'Losartana',
  description: '',
  medication: null,
  capsule_quantity: null,
  progress_trend: '',
  missed_reason: '',
  is_exception: false,
  date: '2026-01-10',
  time: '08:00',
  recurrence: 'none',
  repeat_until: null,
  status: 'pending',
  caregiver: '',
  created_by: 7,
  timestamp: '2026-01-10T08:00:00Z',
  recurrence_group: null,
  author_name: 'Ana Cuidadora',
  medication_detail: '',
  is_from_series: false,
  social: { counts: {}, user_reaction: '', comments: 0 },
  ...overrides,
});

describe('RecordListScreen - filtros combinaveis do historico', () => {
  afterEach(async () => {
    // Da tempo para timers internos do FlatList/VirtualizedList (agendados
    // via setTimeout) e promises pendentes se resolverem antes do proximo
    // teste montar uma nova instancia, evitando vazamento entre testes.
    await new Promise((resolve) => setTimeout(resolve, 50));
  });

  beforeEach(() => {
    jest.clearAllMocks();
    (recordsApi.list as jest.Mock).mockResolvedValue({
      data: { count: 1, next: null, previous: null, results: [mockRecord()] },
    });
    (recordsApi.authors as jest.Mock).mockResolvedValue({
      data: [
        { id: 7, name: 'Ana Cuidadora' },
        { id: 9, name: 'Bruno Familiar' },
      ],
    });
  });

  it('carrega a lista sem filtro nenhum na primeira renderizacao', async () => {
    const { findByText } = await render(<RecordListScreen />);

    await findByText('Losartana', {}, { timeout: 5000 });

    expect(recordsApi.list).toHaveBeenCalledWith(
      expect.objectContaining({ page: '1' }),
    );
    const firstCallParams = (recordsApi.list as jest.Mock).mock.calls[0][0];
    expect(firstCallParams.type).toBeUndefined();
    expect(firstCallParams.date_from).toBeUndefined();
    expect(firstCallParams.date_to).toBeUndefined();
    expect(firstCallParams.author).toBeUndefined();
  });

  it('abre o painel de filtros e busca a lista de autores do grupo', async () => {
    const { getByText, findByText } = await render(<RecordListScreen />);
    await findByText('Losartana', {}, { timeout: 5000 });

    fireEvent.press(getByText(/^Filtros/));

    await findByText('Bruno Familiar', {}, { timeout: 5000 });
    expect(recordsApi.authors).toHaveBeenCalled();
  });

  it('aplica filtro de tipo e atualiza a lista imediatamente', async () => {
    const { getAllByText, findByText } = await render(<RecordListScreen />);
    await findByText('Losartana', {}, { timeout: 5000 });
    (recordsApi.list as jest.Mock).mockClear();

    fireEvent.press(getAllByText('Remédio')[0]);

    await waitFor(() => {
      expect(recordsApi.list).toHaveBeenCalledWith(
        expect.objectContaining({ type: 'medication' }),
      );
    });
  });

  it('combina filtro de tipo, intervalo de datas e autor em uma unica chamada', async () => {
    const { getByText, getAllByText, findByText } = await render(<RecordListScreen />);
    await findByText('Losartana', {}, { timeout: 5000 });

    fireEvent.press(getAllByText('Remédio')[0]);
    await waitFor(() => {
      expect(recordsApi.list).toHaveBeenCalledWith(expect.objectContaining({ type: 'medication' }));
    });

    fireEvent.press(getByText(/^Filtros/));
    await findByText('Bruno Familiar', {}, { timeout: 5000 });

    fireEvent.press(getByText('selecionar-Data Inicial'));
    await waitFor(() => {
      expect(recordsApi.list).toHaveBeenCalledWith(
        expect.objectContaining({ date_from: '2026-01-08' }),
      );
    });

    fireEvent.press(getByText('selecionar-Data Final'));
    await waitFor(() => {
      expect(recordsApi.list).toHaveBeenCalledWith(
        expect.objectContaining({ date_from: '2026-01-08', date_to: '2026-01-08' }),
      );
    });

    fireEvent.press(getByText('Bruno Familiar'));
    await waitFor(() => {
      const lastCall = (recordsApi.list as jest.Mock).mock.calls.slice(-1)[0][0];
      expect(lastCall).toEqual(
        expect.objectContaining({
          type: 'medication',
          date_from: '2026-01-08',
          date_to: '2026-01-08',
          author: '9',
        }),
      );
    });
  });

  it('mostra indicacao visual de filtros ativos e permite limpa-los, voltando ao estado inicial', async () => {
    const { getByText, getAllByText, findByText, queryByText } = await render(<RecordListScreen />);
    await findByText('Losartana', {}, { timeout: 5000 });

    fireEvent.press(getAllByText('Remédio')[0]);
    fireEvent.press(getByText(/^Filtros/));
    await findByText('Bruno Familiar', {}, { timeout: 5000 });
    fireEvent.press(getByText('Bruno Familiar'));

    await findByText('2 filtros ativos', {}, { timeout: 5000 });

    fireEvent.press(getByText('Limpar filtros'));

    await waitFor(() => {
      expect(queryByText(/filtros ativos/)).toBeNull();
    });

    const lastCall = (recordsApi.list as jest.Mock).mock.calls.slice(-1)[0][0];
    expect(lastCall.type).toBeUndefined();
    expect(lastCall.author).toBeUndefined();
    expect(lastCall.date_from).toBeUndefined();
    expect(lastCall.date_to).toBeUndefined();
  });
});
