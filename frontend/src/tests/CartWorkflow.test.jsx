import React from 'react';
import { render } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import CartWorkflow from '../components/CartWorkflow';

// CartWorkflow is a redirect-only component — it renders null and immediately
// navigates to /place-order. The test verifies it mounts without errors.
test('renders CartWorkflow without crashing', () => {
  const { container } = render(
    <MemoryRouter>
      <CartWorkflow />
    </MemoryRouter>
  );
  expect(container.firstChild).toBeNull();
});