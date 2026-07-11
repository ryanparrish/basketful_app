/**
 * VariablesPanel: renders tokens with friendly labels, copies {{ token }}
 * to the clipboard, and badges list-kind variables as code-mode-only.
 */
import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { VariablesPanel, type EmailVariableInfo } from '../VariablesPanel';

const VARIABLES: EmailVariableInfo[] = [
  {
    token: 'user.first_name',
    label: "Recipient's first name",
    description: 'First name of the person receiving the email.',
    sample_value: 'Maria',
    kind: 'value',
  },
  {
    token: 'products',
    label: 'Low-stock products',
    description: 'Loop with {% for %}.',
    sample_value: null,
    kind: 'list',
  },
];

describe('VariablesPanel', () => {
  it('renders labels and monospace tokens', () => {
    render(<VariablesPanel variables={VARIABLES} />);
    expect(screen.getByText("Recipient's first name")).toBeInTheDocument();
    expect(screen.getByText('{{ user.first_name }}')).toBeInTheDocument();
  });

  it('badges list variables as code mode only and gives them no copy button', () => {
    render(<VariablesPanel variables={VARIABLES} />);
    expect(screen.getByText('code mode only')).toBeInTheDocument();
    expect(screen.queryByLabelText('Copy Low-stock products')).not.toBeInTheDocument();
  });

  it('copies the wrapped token to the clipboard', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.assign(navigator, { clipboard: { writeText } });
    render(<VariablesPanel variables={VARIABLES} />);
    fireEvent.click(screen.getByLabelText("Copy Recipient's first name"));
    expect(writeText).toHaveBeenCalledWith('{{ user.first_name }}');
  });

  it('prefers onInsert when provided', () => {
    const onInsert = vi.fn();
    render(<VariablesPanel variables={VARIABLES} onInsert={onInsert} />);
    fireEvent.click(screen.getByLabelText("Copy Recipient's first name"));
    expect(onInsert).toHaveBeenCalledWith('user.first_name');
  });
});
