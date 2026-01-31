import { render, screen, fireEvent } from '@testing-library/react';
import { CartProvider } from 'react-use-cart';
import ParticipantCart from '../components/ParticipantCart';

test('renders ParticipantCart with empty cart', () => {
  render(
    <CartProvider>
      <ParticipantCart />
    </CartProvider>
  );
  const emptyMessage = screen.getByText(/Your cart is empty/i);
  expect(emptyMessage).toBeInTheDocument();
});

test('renders ParticipantCart with items', () => {
  const initialCartState = {
    isEmpty: false,
    totalUniqueItems: 2,
    items: [
      { id: 1, name: 'Item 1', quantity: 1, price: 10 },
      { id: 2, name: 'Item 2', quantity: 2, price: 15 }
    ],
    cartTotal: 40
  };

  render(
    <CartProvider {...initialCartState}>
      <ParticipantCart />
    </CartProvider>
  );

  const totalItems = screen.getByText(/Total Items: 2/i);
  expect(totalItems).toBeInTheDocument();

  const totalPrice = screen.getByText(/Total: \$40/i);
  expect(totalPrice).toBeInTheDocument();
});