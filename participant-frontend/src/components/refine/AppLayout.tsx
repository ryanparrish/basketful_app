/**
 * Signed-in page chrome: header, sider (desktop) or bottom cart bar (phone),
 * and the one cart drawer both of them open.
 *
 * Must render inside CartProvider/ValidationProvider.
 */
import React, { useState } from 'react';
import { useMediaQuery, useTheme } from '@mui/material';
import { ThemedLayout } from '@refinedev/mui';
import { CustomHeader } from './CustomHeader';
import { CustomSider } from './CustomSider';
import { MobileCartBar, MOBILE_CART_BAR_HEIGHT } from './MobileCartBar';
import { CartDrawer } from '../../features/cart';

export const AppLayout: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('md'));
  const [cartOpen, setCartOpen] = useState(false);

  return (
    <>
      <CustomHeader onCartClick={() => setCartOpen((open) => !open)} />
      <ThemedLayout
        Sider={() => <CustomSider />}
        Header={() => null}
        Footer={() => null}
        childrenBoxProps={{
          sx: {
            p: 0,
            pt: '64px', // Offset for fixed header
            // Keep the last row of products clear of the fixed cart bar
            pb: isMobile ? `${MOBILE_CART_BAR_HEIGHT + 16}px` : 0,
          },
        }}
      >
        {children}
      </ThemedLayout>
      {isMobile && <MobileCartBar onOpenCart={() => setCartOpen(true)} />}
      <CartDrawer open={cartOpen} onClose={() => setCartOpen(false)} />
    </>
  );
};
