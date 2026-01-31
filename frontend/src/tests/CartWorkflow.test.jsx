import React from 'react';
import { render, screen } from '@testing-library/react';
import CartWorkflow from '../components/CartWorkflow';

test('renders CartWorkflow', () => {
  render(<CartWorkflow />);
  const headingElement = screen.getByRole('heading', { name: /Cart Workflow/i });
  expect(headingElement).to.exist;
});