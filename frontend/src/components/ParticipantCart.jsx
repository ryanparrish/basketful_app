import React from 'react';
import { useCart } from 'react-use-cart';

const ParticipantCart = () => {
  const {
    isEmpty,
    totalUniqueItems,
    items,
    cartTotal,
    updateItemQuantity,
    removeItem,
    emptyCart
  } = useCart();

  if (isEmpty) return <h2>Your cart is empty</h2>;

  return (
    <div>
      <h1>Participant Cart</h1>
      <p>Total Items: {totalUniqueItems}</p>
      <ul>
        {items.map((item) => (
          <li key={item.id}>
            {item.name} - {item.quantity} x ${item.price}
            <button onClick={() => updateItemQuantity(item.id, item.quantity - 1)}>-</button>
            <button onClick={() => updateItemQuantity(item.id, item.quantity + 1)}>+</button>
            <button onClick={() => removeItem(item.id)}>Remove</button>
          </li>
        ))}
      </ul>
      <h2>Total: ${cartTotal}</h2>
      <button onClick={emptyCart}>Empty Cart</button>
    </div>
  );
};

export default ParticipantCart;