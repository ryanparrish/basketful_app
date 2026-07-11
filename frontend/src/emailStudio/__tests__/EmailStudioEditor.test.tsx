/**
 * Smoke test: the vendored block editor mounts with an empty document
 * and calls onChange when the store's document changes. Guards vendored
 * code and upstream package upgrades — no upstream internals tested.
 */
import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import {
  EMPTY_EMAIL_MESSAGE,
  EmailStudioEditor,
} from '../EmailStudioEditor';
import { setDocument } from '../vendor/documents/editor/EditorContext';

describe('EmailStudioEditor', () => {
  it('renders the empty canvas without crashing', () => {
    render(<EmailStudioEditor document={EMPTY_EMAIL_MESSAGE} onChange={() => {}} />);
    // The inspector panel's tabs are part of the editor chrome.
    expect(screen.getByText('Styles')).toBeInTheDocument();
  });

  it('notifies onChange when the document changes', () => {
    const onChange = vi.fn();
    render(<EmailStudioEditor document={EMPTY_EMAIL_MESSAGE} onChange={onChange} />);
    setDocument({
      'new-block': { type: 'Text', data: { props: { text: 'hi' } } },
    } as never);
    expect(onChange).toHaveBeenCalled();
  });
});
