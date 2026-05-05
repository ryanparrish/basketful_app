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
  LocationOn,
  Phone,
  Email as EmailIcon,
  CalendarToday,
  AccessTime,
} from '@mui/icons-material';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { useAuth } from '../providers/AuthContext';
import { getBalances, getProfile } from '../shared/api/endpoints';
import { GRID_COLUMNS, PAGE_PADDING, useFullWidth } from '../shared/constants/layout';
import type { Balances } from '../shared/types/api';

const BALANCE_CARDS: {
  key: keyof Balances | 'total_budget';
  label: string;
  subtitle: string;
  bg: string;
}[] = [
  {
    key: 'total_budget',
    label: 'Full Balance',
    subtitle: 'Your total available spending power',
    bg: '#00BCD4',
  },
  {
    key: 'available_balance',
    label: 'Available Balance',
    subtitle: 'Ready to use on your next order',
    bg: '#1976D2',
  },
  {
    key: 'hygiene_balance',
    label: 'Hygiene Balance',
    subtitle: 'For personal care & hygiene items',
    bg: '#F59E0B',
  },
  {
    key: 'go_fresh_balance',
    label: 'Go Fresh Balance',
    subtitle: 'For fresh produce & perishables',
    bg: '#4CAF50',
  },
];

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

  const { data: profile, isLoading: profileLoading } = useQuery({
    queryKey: ['me-profile'],
    queryFn: getProfile,
    staleTime: 5 * 60 * 1000,
  });

  const handleLogout = async () => {
    await logout();
    navigate('/login');
  };

  const handleViewOrders = () => {
    navigate('/orders');
  };

  const getUserInitials = () => {
    if (!user) return '?';
    const first = user.first_name?.[0] || '';
    const last = user.last_name?.[0] || '';
    return (first + last).toUpperCase() || user.customer_number?.[0] || '?';
  };

  const formatMeetingDay = (day: string) =>
    day.charAt(0).toUpperCase() + day.slice(1);

  const formatTime = (timeStr: string) => {
    const [h, m] = timeStr.split(':').map(Number);
    const ampm = h >= 12 ? 'PM' : 'AM';
    const hour = h % 12 || 12;
    return `${hour}:${String(m).padStart(2, '0')} ${ampm}`;
  };

  const getBalanceValue = (key: string): number => {
    if (!balances) return 0;
    return Number(balances[key as keyof Balances]) || 0;
  };

  return (
    <Box
      sx={{
        ...useFullWidth(),
        py: PAGE_PADDING.y,
        pb: PAGE_PADDING.bottom,
        px: PAGE_PADDING.x,
      }}
    >
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

        {/* Right Column */}
        <Grid size={GRID_COLUMNS.ACCOUNT_CONTENT} sx={{ flex: 1 }}>
          {/* Balance Cards */}
          <Box sx={{ mb: 3 }}>
            <Stack direction="row" alignItems="center" spacing={1} sx={{ mb: 2 }}>
              <AccountBalance color="primary" />
              <Typography variant="h6">Your Balances</Typography>
            </Stack>

            {balancesLoading ? (
              <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
                <CircularProgress />
              </Box>
            ) : balances ? (
              <Grid container spacing={2}>
                {BALANCE_CARDS.map((card) => (
                  <Grid key={card.key} size={{ xs: 12, sm: 6, md: 3 }}>
                    <Paper
                      elevation={3}
                      sx={{
                        p: 2.5,
                        bgcolor: card.bg,
                        color: '#fff',
                        borderRadius: 2,
                        height: '100%',
                        display: 'flex',
                        flexDirection: 'column',
                        justifyContent: 'space-between',
                        minHeight: 130,
                      }}
                    >
                      <Typography
                        variant="body2"
                        sx={{ opacity: 0.9, fontWeight: 600, letterSpacing: 0.3 }}
                        gutterBottom
                      >
                        {card.label}
                      </Typography>
                      <Typography variant="h4" fontWeight={700} sx={{ my: 0.5 }}>
                        ${getBalanceValue(card.key).toFixed(2)}
                      </Typography>
                      <Typography variant="caption" sx={{ opacity: 0.8 }}>
                        {card.subtitle}
                      </Typography>
                    </Paper>
                  </Grid>
                ))}
              </Grid>
            ) : (
              <Typography color="text.secondary">
                Unable to load balance information
              </Typography>
            )}
          </Box>

          {/* Program & Coach Info */}
          {profileLoading ? (
            <Box sx={{ display: 'flex', justifyContent: 'center', py: 2 }}>
              <CircularProgress size={24} />
            </Box>
          ) : (
            <>
              {profile?.program && (
                <Card sx={{ mb: 3 }}>
                  <CardContent>
                    <Typography variant="h6" gutterBottom>
                      Your Program
                    </Typography>
                    <Typography variant="subtitle1" fontWeight={600} sx={{ mb: 1.5 }}>
                      {profile.program.name}
                    </Typography>
                    <Stack spacing={1}>
                      <Stack direction="row" spacing={1} alignItems="center">
                        <CalendarToday fontSize="small" color="action" />
                        <Typography variant="body2">
                          {formatMeetingDay(profile.program.meeting_day)}s
                        </Typography>
                      </Stack>
                      <Stack direction="row" spacing={1} alignItems="center">
                        <AccessTime fontSize="small" color="action" />
                        <Typography variant="body2">
                          {formatTime(profile.program.meeting_time)}
                        </Typography>
                      </Stack>
                      {profile.program.meeting_address && (
                        <Stack direction="row" spacing={1} alignItems="center">
                          <LocationOn fontSize="small" color="action" />
                          <Typography variant="body2">
                            {profile.program.meeting_address}
                          </Typography>
                        </Stack>
                      )}
                    </Stack>
                  </CardContent>
                </Card>
              )}

              {profile?.coach && (
                <Card sx={{ mb: 3 }}>
                  <CardContent>
                    <Typography variant="h6" gutterBottom>
                      Your Life Skills Leader
                    </Typography>
                    <Stack direction="row" spacing={2} alignItems="center">
                      <Avatar
                        src={profile.coach.image || undefined}
                        sx={{
                          width: 64,
                          height: 64,
                          bgcolor: 'secondary.main',
                          fontSize: '1.5rem',
                        }}
                      >
                        {profile.coach.name[0]}
                      </Avatar>
                      <Box>
                        <Typography variant="subtitle1" fontWeight={600}>
                          {profile.coach.name}
                        </Typography>
                        <Stack spacing={0.5} sx={{ mt: 0.5 }}>
                          <Stack direction="row" spacing={0.75} alignItems="center">
                            <EmailIcon fontSize="small" color="action" />
                            <Typography
                              variant="body2"
                              component="a"
                              href={`mailto:${profile.coach.email}`}
                              sx={{ color: 'primary.main', textDecoration: 'none' }}
                            >
                              {profile.coach.email}
                            </Typography>
                          </Stack>
                          {profile.coach.phone_number && (
                            <Stack direction="row" spacing={0.75} alignItems="center">
                              <Phone fontSize="small" color="action" />
                              <Typography
                                variant="body2"
                                component="a"
                                href={`tel:${profile.coach.phone_number}`}
                                sx={{ color: 'primary.main', textDecoration: 'none' }}
                              >
                                {profile.coach.phone_number}
                              </Typography>
                            </Stack>
                          )}
                        </Stack>
                      </Box>
                    </Stack>
                  </CardContent>
                </Card>
              )}
            </>
          )}

          {/* Mobile Actions */}
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
