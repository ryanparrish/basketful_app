/**
 * CartWorkflow
 *
 * Thin redirect wrapper — the full staff cart workflow lives in
 * StaffOrderPage.tsx. Navigate to /place-order to use it.
 */
import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';

const CartWorkflow = () => {
  const navigate = useNavigate();
  useEffect(() => {
    navigate('/place-order', { replace: true });
  }, [navigate]);
  return null;
};

export default CartWorkflow;