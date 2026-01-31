import React from 'react';
import { render, screen } from '@testing-library/react';
import OrderWorkflow from '../components/OrderWorkflow';

test('renders OrderWorkflow', () => {
  render(<OrderWorkflow />);
  const headingElement = screen.getByRole('heading', { name: /Order Workflow/i });
  expect(headingElement).to.exist;
});