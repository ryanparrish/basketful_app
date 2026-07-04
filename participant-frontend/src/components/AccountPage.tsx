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
import { useTranslation } from 'react-i18next';
import { useAuth } from '../providers/AuthContext';
import { getBalances, getProfile } from '../shared/api/endpoints';
import { useFormatters } from '../shared/hooks/useFormatters';
import { translateDynamic } from '../i18n';
import { LanguageSwitcher } from './LanguageSwitcher';
import { GRID_COLUMNS, PAGE_PADDING, useFullWidth } from '../shared/constants/layout';
import type { Balances } from '../shared/types/api';

// Holds i18n key references, never translated strings — module-level
// constants must not capture a language
const BALANCE_CARDS = [
  { key: 'full_balance', bg: '#00BCD4' },
  { key: 'available_balance', bg: '#1976D2' },
  { key: 'hygiene_balance', bg: '#F59E0B' },
  { key: 'go_fresh_balance', bg: '#4CAF50' },
] as const;

export const AccountPage: React.FC = () => {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const { formatCurrency, formatTimeOfDay } = useFormatters();
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

  // Backend sends English day names (e.g. "monday"); translate via the
  // days catalog, falling back to a capitalized version of the raw value
  const formatMeetingDay = (day: string) =>
    translateDynamic(`days.${day.toLowerCase()}`, {
      defaultValue: day.charAt(0).toUpperCase() + day.slice(1),
    });

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
              {t('account.customerNumber', { number: user?.customer_number ?? '' })}
            </Typography>
            {user?.email && (
              <Typography variant="body2" color="text.secondary">
                {user.email}
              </Typography>
            )}

            {isDesktop && (
              <Stack spacing={2} sx={{ mt: 3 }}>
                <Divider />
                <LanguageSwitcher variant="select" />
                <Button
                  variant="outlined"
                  startIcon={<ShoppingBag />}
                  onClick={handleViewOrders}
                  fullWidth
                >
                  {t('account.viewOrderHistory')}
                </Button>
                <Button
                  variant="contained"
                  color="error"
                  startIcon={<Logout />}
                  onClick={handleLogout}
                  fullWidth
                >
                  {t('common.signOut')}
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
              <Typography variant="h6">{t('account.yourBalances')}</Typography>
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
                        {t(`account.balances.${card.key}.label`)}
                      </Typography>
                      <Typography variant="h4" fontWeight={700} sx={{ my: 0.5 }}>
                        {formatCurrency(getBalanceValue(card.key))}
                      </Typography>
                      <Typography variant="caption" sx={{ opacity: 0.8 }}>
                        {t(`account.balances.${card.key}.subtitle`)}
                      </Typography>
                    </Paper>
                  </Grid>
                ))}
              </Grid>
            ) : (
              <Typography color="text.secondary">
                {t('account.balanceLoadFailed')}
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
                      {t('account.yourProgram')}
                    </Typography>
                    <Typography variant="subtitle1" fontWeight={600} sx={{ mb: 1.5 }}>
                      {profile.program.name}
                    </Typography>
                    <Stack spacing={1}>
                      <Stack direction="row" spacing={1} alignItems="center">
                        <CalendarToday fontSize="small" color="action" />
                        <Typography variant="body2">
                          {t('account.weeklyMeetingDay', {
                            day: formatMeetingDay(profile.program.meeting_day),
                          })}
                        </Typography>
                      </Stack>
                      <Stack direction="row" spacing={1} alignItems="center">
                        <AccessTime fontSize="small" color="action" />
                        <Typography variant="body2">
                          {formatTimeOfDay(profile.program.meeting_time)}
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
                      {t('account.yourCoach')}
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
              <LanguageSwitcher variant="select" />

              <Button
                variant="outlined"
                size="large"
                startIcon={<ShoppingBag />}
                onClick={handleViewOrders}
                fullWidth
              >
                {t('account.viewOrderHistory')}
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
                {t('common.signOut')}
              </Button>
            </Stack>
          )}
        </Grid>
      </Grid>
    </Box>
  );
};

export default AccountPage;
