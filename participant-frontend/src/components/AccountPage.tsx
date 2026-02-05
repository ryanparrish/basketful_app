/**
 * Account Page
 * User account info and settings
 */
import React from 'react';
import {
  Container,
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

export const AccountPage: React.FC = () => {
  const navigate = useNavigate();
  const { user, logout } = useAuth();

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
    <Container maxWidth="sm" sx={{ py: 3, pb: 10 }}>
      {/* Profile Card */}
      <Paper sx={{ p: 3, mb: 3, textAlign: 'center' }}>
        <Avatar
          sx={{
            width: 80,
            height: 80,
            fontSize: '2rem',
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
      </Paper>

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
            <Stack spacing={1}>
              <Stack direction="row" justifyContent="space-between">
                <Typography color="text.secondary">Total Budget:</Typography>
                <Typography fontWeight={500}>${balances.total_budget.toFixed(2)}</Typography>
              </Stack>
              <Stack direction="row" justifyContent="space-between">
                <Typography color="text.secondary">Used:</Typography>
                <Typography fontWeight={500}>${balances.used_budget.toFixed(2)}</Typography>
              </Stack>
              <Divider />
              <Stack direction="row" justifyContent="space-between">
                <Typography fontWeight={600}>Remaining:</Typography>
                <Typography
                  fontWeight={600}
                  color={balances.remaining_budget > 0 ? 'success.main' : 'error.main'}
                >
                  ${balances.remaining_budget.toFixed(2)}
                </Typography>
              </Stack>
              {balances.grace_allowance !== undefined && balances.grace_allowance > 0 && (
                <Stack direction="row" justifyContent="space-between">
                  <Typography variant="body2" color="text.secondary">
                    Grace Allowance:
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    ${balances.grace_allowance.toFixed(2)}
                  </Typography>
                </Stack>
              )}
            </Stack>
          ) : (
            <Typography color="text.secondary">Unable to load budget information</Typography>
          )}
        </CardContent>
      </Card>

      {/* Quick Actions */}
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
    </Container>
  );
};

export default AccountPage;
