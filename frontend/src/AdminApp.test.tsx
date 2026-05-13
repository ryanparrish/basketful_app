import { render, screen } from '@testing-library/react';
import AdminApp from './AdminApp';

describe('AdminApp', () => {
  it('renders admin app', () => {
    render(<AdminApp />);
    // The sidebar renders both "Dashboard" and "Coach Dashboard" — check at least one exists.
    expect(screen.getAllByText(/dashboard/i).length).toBeGreaterThan(0);
  });
});
