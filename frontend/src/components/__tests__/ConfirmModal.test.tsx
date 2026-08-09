import React from 'react';
import { render, fireEvent } from '@testing-library/react-native';
import ConfirmModal from '../ConfirmModal';
import { colors } from '../../theme';

/** Achata um `style` (que pode ser array de objetos) num único objeto. */
function flattenStyle(style: any): Record<string, unknown> {
  if (!style) return {};
  if (Array.isArray(style)) {
    return style.reduce((acc, s) => ({ ...acc, ...flattenStyle(s) }), {});
  }
  return style;
}

/** Percorre a árvore renderizada (toJSON()) procurando o nó `Modal`. */
function findModalNode(node: any): any {
  if (!node) return null;
  if (Array.isArray(node)) {
    for (const child of node) {
      const found = findModalNode(child);
      if (found) return found;
    }
    return null;
  }
  if (node.type === 'Modal') return node;
  if (node.children) return findModalNode(node.children);
  return null;
}

/** Acha, dentro de uma subárvore, o primeiro nó cujo style tenha `key`. */
function findNodeWithStyleKey(node: any, key: string): any {
  if (!node) return null;
  if (Array.isArray(node)) {
    for (const child of node) {
      const found = findNodeWithStyleKey(child, key);
      if (found) return found;
    }
    return null;
  }
  const flat = flattenStyle(node.props && node.props.style);
  if (Object.prototype.hasOwnProperty.call(flat, key)) return node;
  if (node.children) return findNodeWithStyleKey(node.children, key);
  return null;
}

describe('ConfirmModal', () => {
  it('exibe o título e a mensagem quando visible=true', async () => {
    const { getByText } = await render(
      <ConfirmModal
        visible
        title="Excluir registro"
        message="Tem certeza que deseja excluir este registro?"
        onConfirm={() => {}}
        onCancel={() => {}}
      />
    );

    expect(getByText('Excluir registro')).toBeTruthy();
    expect(getByText('Tem certeza que deseja excluir este registro?')).toBeTruthy();
  });

  it('não renderiza o conteúdo quando visible=false', async () => {
    const { queryByText, toJSON } = await render(
      <ConfirmModal
        visible={false}
        title="Excluir registro"
        message="Tem certeza que deseja excluir este registro?"
        onConfirm={() => {}}
        onCancel={() => {}}
      />
    );

    expect(queryByText('Excluir registro')).toBeNull();
    expect(queryByText('Tem certeza que deseja excluir este registro?')).toBeNull();
    // O mock oficial de `Modal` (react-native/jest/mocks/Modal.js) não
    // renderiza a subárvore quando `visible` é false.
    expect(findModalNode(toJSON())).toBeNull();
  });

  it('renderiza um Modal transparente com um overlay quando visible=true', async () => {
    const { toJSON } = await render(
      <ConfirmModal
        visible
        title="Excluir registro"
        message="Confirma?"
        onConfirm={() => {}}
        onCancel={() => {}}
      />
    );

    const modalNode = findModalNode(toJSON());
    expect(modalNode).toBeTruthy();
    expect(modalNode.props.transparent).toBe(true);
    expect(modalNode.props.visible).toBe(true);

    // O overlay é o contêiner semi-transparente que cobre a tela atrás do
    // cartão de conteúdo do modal.
    const overlayNode = findNodeWithStyleKey(modalNode, 'backgroundColor');
    expect(overlayNode).toBeTruthy();
    const overlayStyle = flattenStyle(overlayNode.props.style);
    expect(typeof overlayStyle.backgroundColor).toBe('string');
    expect(String(overlayStyle.backgroundColor)).not.toBe(colors.surface);
  });

  it('chama onConfirm ao tocar no botão de confirmar', async () => {
    const onConfirm = jest.fn();
    const { getByText } = await render(
      <ConfirmModal
        visible
        title="Excluir registro"
        message="Confirma?"
        confirmText="Excluir"
        onConfirm={onConfirm}
        onCancel={() => {}}
      />
    );

    fireEvent.press(getByText('Excluir'));

    expect(onConfirm).toHaveBeenCalledTimes(1);
  });

  it('chama onCancel ao tocar no botão de cancelar', async () => {
    const onCancel = jest.fn();
    const { getByText } = await render(
      <ConfirmModal
        visible
        title="Excluir registro"
        message="Confirma?"
        cancelText="Cancelar"
        onConfirm={() => {}}
        onCancel={onCancel}
      />
    );

    fireEvent.press(getByText('Cancelar'));

    expect(onCancel).toHaveBeenCalledTimes(1);
  });

  it('usa os textos padrão de confirmar e cancelar quando não informados', async () => {
    const { getByText } = await render(
      <ConfirmModal
        visible
        title="Excluir registro"
        message="Confirma?"
        onConfirm={() => {}}
        onCancel={() => {}}
      />
    );

    expect(getByText('Confirmar')).toBeTruthy();
    expect(getByText('Cancelar')).toBeTruthy();
  });

  it('aplica a cor de perigo do tema (colors.danger) ao botão de confirmar quando destructive=true', async () => {
    const { getByTestId } = await render(
      <ConfirmModal
        visible
        title="Excluir registro"
        message="Confirma?"
        destructive
        onConfirm={() => {}}
        onCancel={() => {}}
      />
    );

    const confirmButton = getByTestId('confirm-modal-confirm-button');
    const flatStyle = flattenStyle(confirmButton.props.style);

    expect(flatStyle.backgroundColor).toBe(colors.danger);
  });

  it('não aplica a cor de perigo do tema ao botão de confirmar quando destructive não é informado', async () => {
    const { getByTestId } = await render(
      <ConfirmModal
        visible
        title="Excluir registro"
        message="Confirma?"
        onConfirm={() => {}}
        onCancel={() => {}}
      />
    );

    const confirmButton = getByTestId('confirm-modal-confirm-button');
    const flatStyle = flattenStyle(confirmButton.props.style);

    expect(flatStyle.backgroundColor).not.toBe(colors.danger);
  });
});
