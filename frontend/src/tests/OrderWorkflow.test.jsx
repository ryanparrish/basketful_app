import { render, screen } from '@testing-library/react';
import OrderWorkflow from '../components/OrderWorkflow';

test('renders OrderWorkflow', () => {
  render(<OrderWorkflow />);
  const headingElement = screen.getByText(/Order Workflow/i);
  expect(headingElement).toBeInTheDocument();
});