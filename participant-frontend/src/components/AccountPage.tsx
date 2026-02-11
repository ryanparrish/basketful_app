/**
 * Account Page
 * User account info and settings with responsive desktop layout
 */
import React from 'react';
import {
  Paper,
  Typography,
  Box,
  Button,
  Card,
  CardContent,
  Stack,
  Divider,
  Avatar,
  CircularProgress,
  Grid,
  useMediaQuery,
  useTheme,
} from '@mui/material';
import {
  Logout,
  AccountBalance,
  ShoppingBag,
} from '@mui/icons-material';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { useAuth } from '../providers/AuthContext';
import { getBalances } from '../shared/api/endpoints';
import { GRID_COLUMNS, PAGE_PADDING, useFullWidth } from '../shared/constants/layout';

export const AccountPage: React.FC = () => {
  const navigate = useNavigate();
  const { user, logout } = useAuth();
  const theme = useTheme();
  const isDesktop = useMediaQuery(theme.breakpoints.up('lg'));

  const { data: balances, isLoading: balancesLoading } = useQuery({
    queryKey: ['balances'],
    queryFn: getBalances,
    staleTime: 30 * 1000,
  });

  const handleLogout = async () => {
    await logout();
    navigate('/login');
  };

  const handleViewOrders = () => {
    navigate('/orders');
  };

  // Get user initials for avatar
  const getUserInitials = () => {
    if (!user) return '?';
    const first = user.first_name?.[0] || '';
    const last = user.last_name?.[0] || '';
    return (first + last).toUpperCase() || user.customer_number?.[0] || '?';
  };

  return (
    <Box sx={{ 
      ...useFullWidth(),
      py: PAGE_PADDING.y,
      pb: PAGE_PADDING.bottom,
      px: PAGE_PADDING.x,
    }}>
      <Grid container spacing={3}>
        {/* Left Column - Profile */}
        <Grid size={GRID_COLUMNS.ACCOUNT_PROFILE}>
          <Paper sx={{ p: 3, textAlign: 'center', height: '100%' }}>
            <Avatar
              sx={{
                width: 100,
                height: 100,
                fontSize: '2.5rem',
                bgcolor: 'primary.main',
                mx: 'auto',
                mb: 2,
              }}
            >
              {getUserInitials()}
            </Avatar>
            <Typography variant="h5" gutterBottom>
              {user?.first_name} {user?.last_name}
            </Typography>
            <Typography variant="body2" color="text.secondary">
              Customer # {user?.customer_number}
            </Typography>
            {user?.email && (
              <Typography variant="body2" color="text.secondary">
                {user.email}
              </Typography>
            )}
            
            {/* Actions on desktop - inside profile card */}
            {isDesktop && (
              <Stack spacing={2} sx={{ mt: 3 }}>
                <Divider />
                <Button
                  variant="outlined"
                  startIcon={<ShoppingBag />}
                  onClick={handleViewOrders}
                  fullWidth
                >
                  View Order History
                </Button>
                <Button
                  variant="contained"
                  color="error"
                  startIcon={<Logout />}
                  onClick={handleLogout}
                  fullWidth
                >
                  Sign Out
                </Button>
              </Stack>
            )}
          </Paper>
        </Grid>

        {/* Right Column - Budget & Actions */}
        <Grid size={GRID_COLUMNS.ACCOUNT_CONTENT} sx={{ flex: 1 }}>
          {/* Balance Card */}
          <Card sx={{ mb: 3 }}>
            <CardContent>
              <Stack direction="row" alignItems="center" spacing={1} sx={{ mb: 2 }}>
                <AccountBalance color="primary" />
                <Typography variant="h6">Budget Summary</Typography>
              </Stack>

              {balancesLoading ? (
                <Box sx={{ display: 'flex', justifyContent: 'center', py: 2 }}>
                  <CircularProgress size={24} />
                </Box>
              ) : balances ? (
                <Grid container spacing={2}>
                  <Grid size={{ xs: 12, sm: 6, md: 3 }}>
                    <Paper variant="outlined" sx={{ p: 2, textAlign: 'center', height: '100%' }}>
                      <Typography variant="body2" color="text.secondary" gutterBottom>
                        Total Budget
                      </Typography>
                      <Typography variant="h5" fontWeight={600}>
                        ${balances.total_budget.toFixed(2)}
                      </Typography>
                    </Paper>
                  </Grid>
                  <Grid size={{ xs: 12, sm: 6, md: 3 }}>
                    <Paper variant="outlined" sx={{ p: 2, textAlign: 'center', height: '100%' }}>
                      <Typography variant="body2" color="text.secondary" gutterBottom>
                        Used
                      </Typography>
                      <Typography variant="h5" fontWeight={600}>
                        ${balances.used_budget.toFixed(2)}
                      </Typography>
                    </Paper>
                  </Grid>
                  <Grid size={{ xs: 12, sm: 6, md: 3 }}>
                    <Paper 
                      variant="outlined" 
                      sx={{ 
                        p: 2, 
                        textAlign: 'center',
                        height: '100%',
                        borderColor: balances.remaining_budget > 0 ? 'success.main' : 'error.main',
                        borderWidth: 2,
                      }}
                    >
                      <Typography variant="body2" color="text.secondary" gutterBottom>
                        Remaining
                      </Typography>
                      <Typography 
                        variant="h5" 
                        fontWeight={600}
                        color={balances.remaining_budget > 0 ? 'success.main' : 'error.main'}
                      >
                        ${balances.remaining_budget.toFixed(2)}
                      </Typography>
                    </Paper>
                  </Grid>
                  <Grid size={{ xs: 12, sm: 6, md: 3 }}>
                    <Paper variant="outlined" sx={{ p: 2, textAlign: 'center', height: '100%' }}>
                      <Typography variant="body2" color="text.secondary" gutterBottom>
                        Available
                      </Typography>
                      <Typography variant="h5" fontWeight={600} color="primary">
                        ${balances.available_balance.toFixed(2)}
                      </Typography>
                    </Paper>
                  </Grid>
                  
                  {/* Additional Balance Types */}
                  <Grid size={{ xs: 12, sm: 6, md: 4 }}>
                    <Paper 
                      variant="outlined" 
                      sx={{ 
                        p: 2, 
                        textAlign: 'center',
                        bgcolor: 'info.50',
                        borderColor: 'info.main',
                      }}
                    >
                      <Typography variant="body2" color="text.secondary" gutterBottom>
                        Hygiene Balance
                      </Typography>
                      <Typography variant="h6" fontWeight={600} color="info.main">
                        ${balances.hygiene_balance.toFixed(2)}
                      </Typography>
                    </Paper>
                  </Grid>
                  <Grid size={{ xs: 12, sm: 6, md: 4 }}>
                    <Paper 
                      variant="outlined" 
                      sx={{ 
                        p: 2, 
                        textAlign: 'center',
                        bgcolor: 'success.50',
                        borderColor: 'success.main',
                      }}
                    >
                      <Typography variant="body2" color="text.secondary" gutterBottom>
                        Go Fresh Balance
                      </Typography>
                      <Typography variant="h6" fontWeight={600} color="success.dark">
                        ${balances.go_fresh_balance.toFixed(2)}
                      </Typography>
                    </Paper>
                  </Grid>
                  <Grid size={{ xs: 12, sm: 6, md: 4 }}>
                    <Paper 
                      variant="outlined" 
                      sx={{ 
                        p: 2, 
                        textAlign: 'center',
                        bgcolor: 'secondary.50',
                        borderColor: 'secondary.main',
                      }}
                    >
                      <Typography variant="body2" color="text.secondary" gutterBottom>
                        Full Balance
                      </Typography>
                      <Typography variant="h6" fontWeight={600} color="secondary.main">
                        ${(balances.available_balance + balances.hygiene_balance + balances.go_fresh_balance).toFixed(2)}
                      </Typography>
                    </Paper>
                  </Grid>
                </Grid>
              ) : (
                <Typography color="text.secondary">Unable to load budget information</Typography>
              )}
            </CardContent>
          </Card>

          {/* Quick Actions - only show on mobile */}
          {!isDesktop && (
            <Stack spacing={2}>
              <Button
                variant="outlined"
                size="large"
                startIcon={<ShoppingBag />}
                onClick={handleViewOrders}
                fullWidth
              >
                View Order History
              </Button>

              <Divider />

              <Button
                variant="contained"
                color="error"
                size="large"
                startIcon={<Logout />}
                onClick={handleLogout}
                fullWidth
              >
                Sign Out
              </Button>
            </Stack>
          )}
        </Grid>
      </Grid>
    </Box>
  );
};

export default AccountPage;
