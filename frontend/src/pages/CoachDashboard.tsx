/**
 * Coach Dashboard — personal view for Lifeskills Coaches
 *
 * Shows:
 *  - Order window status for their program
 *  - Summary counts (total / active participants, orders placed vs pending)
 *  - Participant list with recent-order status
 */
import { useEffect, useState } from 'react';
import { useNotify, useGetIdentity } from 'react-admin';
import {
  Box,
  Card,
  CardContent,
  Chip,
  CircularProgress,
  Divider,
  Grid,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Typography,
  Alert,
} from '@mui/material';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import PendingIcon from '@mui/icons-material/Pending';
import LockIcon from '@mui/icons-material/Lock';
import LockOpenIcon from '@mui/icons-material/LockOpen';
import apiClient from '../lib/api/apiClient';

// ─── Types ────────────────────────────────────────────────────────────────────

interface ParticipantStatus {
  id: number;
  name: string;
  customer_number: string | null;
  email: string;
  is_active: boolean;
  has_recent_order: boolean;
  last_order_date: string | null;
  last_order_id: number | null;
}

interface Summary {
  total_participants: number;
  active_participants: number;
  orders_placed_recently: number;
  orders_pending: number;
}

interface WindowStatus {
  window_status: 'open' | 'closed' | 'force_open' | 'force_closed' | 'disabled' | 'no_schedule';
  program_name: string;
  meeting_day: string;
  meeting_time: string;
}

interface DashboardData {
  coach: { name: string; email: string; program_name: string | null };
  window_status: WindowStatus | null;
  participants: ParticipantStatus[];
  summary: Summary;
}

// ─── Window status chip ───────────────────────────────────────────────────────

const WINDOW_LABELS: Record<string, string> = {
  open: 'Open',
  closed: 'Closed',
  force_open: 'Force Open',
  force_closed: 'Force Closed',
  disabled: 'Disabled',
  no_schedule: 'No Schedule',
};

const WINDOW_COLORS: Record<string, 'success' | 'default' | 'warning' | 'error' | 'info'> = {
  open: 'success',
  closed: 'default',
  force_open: 'warning',
  force_closed: 'error',
  disabled: 'info',
  no_schedule: 'default',
};

// ─── Stat card ────────────────────────────────────────────────────────────────

const StatCard = ({
  label,
  value,
  color = 'text.primary',
}: {
  label: string;
  value: number;
  color?: string;
}) => (
  <Card variant="outlined" sx={{ textAlign: 'center', py: 1 }}>
    <CardContent>
      <Typography variant="h3" sx={{ color, fontWeight: 700 }}>
        {value}
      </Typography>
      <Typography variant="body2" color="text.secondary">
        {label}
      </Typography>
    </CardContent>
  </Card>
);

// ─── Main dashboard ───────────────────────────────────────────────────────────

const CoachDashboard = () => {
  const notify = useNotify();
  const { identity } = useGetIdentity();
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiClient
      .get<DashboardData>('/coaches/my-dashboard/')
      .then((res) => setData(res.data))
      .catch((err) => {
        const msg =
          err?.response?.data?.detail ?? 'Failed to load dashboard.';
        setError(msg);
        notify(msg, { type: 'error' });
      })
      .finally(() => setLoading(false));
  }, [notify]);

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', mt: 8 }}>
        <CircularProgress />
      </Box>
    );
  }

  if (error || !data) {
    return (
      <Box sx={{ p: 3 }}>
        <Alert severity="error">
          {error ?? 'No dashboard data available.'}
        </Alert>
      </Box>
    );
  }

  const { coach, window_status, participants, summary } = data;
  const ws = window_status?.window_status ?? 'no_schedule';
  const isOpen = ws === 'open' || ws === 'force_open';

  return (
    <Box sx={{ p: 3 }}>
      {/* Header */}
      <Box sx={{ mb: 3 }}>
        <Typography variant="h4" gutterBottom>
          Coach Dashboard
        </Typography>
        <Typography variant="body1" color="text.secondary">
          Welcome back, <strong>{identity?.fullName ?? coach.name}</strong>
          {coach.program_name && ` · ${coach.program_name}`}
        </Typography>
      </Box>

      {/* Window status banner */}
      <Paper
        variant="outlined"
        sx={{
          p: 2,
          mb: 3,
          display: 'flex',
          alignItems: 'center',
          gap: 2,
          borderColor: isOpen ? 'success.main' : 'divider',
          bgcolor: isOpen ? 'success.50' : 'background.paper',
        }}
      >
        {isOpen ? (
          <LockOpenIcon color="success" fontSize="large" />
        ) : (
          <LockIcon color="disabled" fontSize="large" />
        )}
        <Box>
          <Typography variant="subtitle1" fontWeight={600}>
            Order Window
            {'  '}
            <Chip
              label={WINDOW_LABELS[ws] ?? ws}
              color={WINDOW_COLORS[ws] ?? 'default'}
              size="small"
            />
          </Typography>
          {window_status && (
            <Typography variant="body2" color="text.secondary">
              {window_status.program_name} · {window_status.meeting_day}{' '}
              {window_status.meeting_time}
            </Typography>
          )}
          {!window_status && (
            <Typography variant="body2" color="text.secondary">
              No program assigned.
            </Typography>
          )}
        </Box>
      </Paper>

      {/* Summary stats */}
      {summary && (
        <Grid container spacing={2} sx={{ mb: 3 }}>
          <Grid size={{ xs: 6, sm: 3 }}>
            <StatCard label="Total Participants" value={summary.total_participants} />
          </Grid>
          <Grid size={{ xs: 6, sm: 3 }}>
            <StatCard label="Active" value={summary.active_participants} />
          </Grid>
          <Grid size={{ xs: 6, sm: 3 }}>
            <StatCard
              label="Orders Placed (14d)"
              value={summary.orders_placed_recently}
              color="success.main"
            />
          </Grid>
          <Grid size={{ xs: 6, sm: 3 }}>
            <StatCard
              label="Orders Pending"
              value={summary.orders_pending}
              color={summary.orders_pending > 0 ? 'warning.main' : 'text.primary'}
            />
          </Grid>
        </Grid>
      )}

      <Divider sx={{ mb: 3 }} />

      {/* Participant list */}
      <Typography variant="h6" gutterBottom>
        Participants
      </Typography>

      {participants.length === 0 ? (
        <Alert severity="info">No participants are assigned to you yet.</Alert>
      ) : (
        <TableContainer component={Paper} variant="outlined">
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Name</TableCell>
                <TableCell>Customer #</TableCell>
                <TableCell>Email</TableCell>
                <TableCell>Status</TableCell>
                <TableCell>Order (last 14d)</TableCell>
                <TableCell>Last Order Date</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {participants.map((p) => (
                <TableRow
                  key={p.id}
                  sx={{ opacity: p.is_active ? 1 : 0.5 }}
                >
                  <TableCell>{p.name}</TableCell>
                  <TableCell>{p.customer_number ?? '—'}</TableCell>
                  <TableCell>{p.email}</TableCell>
                  <TableCell>
                    <Chip
                      label={p.is_active ? 'Active' : 'Inactive'}
                      color={p.is_active ? 'success' : 'default'}
                      size="small"
                      variant="outlined"
                    />
                  </TableCell>
                  <TableCell>
                    {p.has_recent_order ? (
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                        <CheckCircleIcon color="success" fontSize="small" />
                        <Typography variant="body2" color="success.main">
                          Placed
                        </Typography>
                      </Box>
                    ) : (
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                        <PendingIcon color="warning" fontSize="small" />
                        <Typography variant="body2" color="warning.main">
                          Pending
                        </Typography>
                      </Box>
                    )}
                  </TableCell>
                  <TableCell>
                    {p.last_order_date
                      ? new Date(p.last_order_date).toLocaleDateString()
                      : '—'}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      )}
    </Box>
  );
};

export default CoachDashboard;
