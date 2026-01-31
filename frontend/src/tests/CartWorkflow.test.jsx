import { render, screen } from '@testing-library/react';
import CartWorkflow from '../components/CartWorkflow';

test('renders CartWorkflow', () => {
  render(<CartWorkflow />);
  const headingElement = screen.getByText(/Cart Workflow/i);
  expect(headingElement).toBeInTheDocument();
});