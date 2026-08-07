import React from 'react';
import { render, fireEvent, waitFor } from '@testing-library/react-native';
import MedicationStockScreen from '../MedicationStockScreen';
import { medicationsApi } from '../../api/endpoints';

jest.mock('../../api/endpoints', () => ({
  medicationsApi: {
    stockOverview: jest.fn(() => Promise.resolve({ data: { sections: [] } })),
    create: jest.fn(() => Promise.resolve({ data: { id: 1, name: 'Paracetamol', dosage: '500mg' } })),
    addStock: jest.fn(() => Promise.resolve({ data: {} })),
  },
}));

describe('MedicationStockScreen - modal Novo Medicamento', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    (medicationsApi.stockOverview as jest.Mock).mockResolvedValue({ data: { sections: [] } });
  });

  it('exibe erros inline para nome e dosagem vazios e não chama a API ao pressionar Criar', async () => {
    const { getByText, findByText, queryByText } = await render(<MedicationStockScreen />);

    // Aguarda o carregamento inicial (loading -> conteúdo)
    await findByText('+ Novo', {}, { timeout: 3000 });

    await fireEvent.press(getByText('+ Novo'));

    const createBtn = await findByText('Criar', {}, { timeout: 3000 });
    await fireEvent.press(createBtn);

    await waitFor(() => {
      expect(queryByText(/informe o nome/i)).toBeTruthy();
      expect(queryByText(/informe a dosagem/i)).toBeTruthy();
    });

    expect(medicationsApi.create).not.toHaveBeenCalled();
  }, 15000);

  it('cria o medicamento com nome e dosagem válidos e fecha o modal', async () => {
    const { getByText, findByText, getByPlaceholderText, queryByText } = await render(
      <MedicationStockScreen />
    );

    await findByText('+ Novo', {}, { timeout: 3000 });
    await fireEvent.press(getByText('+ Novo'));

    const modalTitle = await findByText('Novo Medicamento', {}, { timeout: 3000 });
    expect(modalTitle).toBeTruthy();

    await fireEvent.changeText(getByPlaceholderText('Ex: Paracetamol'), 'Paracetamol');
    await fireEvent.changeText(getByPlaceholderText('Ex: 500mg'), '500mg');

    await fireEvent.press(getByText('Criar'));

    await waitFor(() => {
      expect(medicationsApi.create).toHaveBeenCalledWith({
        name: 'Paracetamol',
        dosage: '500mg',
      });
    });

    await waitFor(() => {
      expect(queryByText('Novo Medicamento')).toBeNull();
    });
  }, 15000);
});
