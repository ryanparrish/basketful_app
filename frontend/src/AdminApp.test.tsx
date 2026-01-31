import { render, screen } from '@testing-library/react';
import AdminApp from './AdminApp';

describe('AdminApp', () => {
  it('renders admin app', () => {
    render(<AdminApp />);
    expect(screen.getByText(/dashboard/i)).toBeInTheDocument();
  });
});
