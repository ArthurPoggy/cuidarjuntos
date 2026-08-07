import React from 'react';
import { render } from '@testing-library/react-native';
import FormField from '../FormField';

describe('FormField', () => {
  it('exibe a mensagem de erro quando a prop error é fornecida', () => {
    const { getByText } = render(
      <FormField label="Nome" value="" onChangeText={() => {}} error="Campo obrigatório" />
    );

    expect(getByText('Campo obrigatório')).toBeTruthy();
  });

  it('não exibe nenhuma mensagem de erro quando a prop error não é fornecida', () => {
    const { queryByText } = render(
      <FormField label="Nome" value="" onChangeText={() => {}} />
    );

    expect(queryByText('Campo obrigatório')).toBeNull();
  });
});
