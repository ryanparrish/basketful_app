import { render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import { vi, describe, it, expect } from 'vitest';
import Dashboard from './Dashboard';

vi.mock('react-admin', () => ({
  useGetList: vi.fn(() => ({
    total: 10,
    isPending: false,
  })),
  Title: () => <div>Title</div>,
  Loading: () => <div>Loading...</div>,
}));

describe('Dashboard page', () => {
  it('renders dashboard title', () => {
    const queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
      },
    });
    render(
      <MemoryRouter>
        <QueryClientProvider client={queryClient}>
          <Dashboard />
        </QueryClientProvider>
      </MemoryRouter>
    );
    // Title is mocked; assert on stat cards that the component actually renders.
    expect(screen.getByText(/Total Participants/i)).toBeDefined();
  });
});
