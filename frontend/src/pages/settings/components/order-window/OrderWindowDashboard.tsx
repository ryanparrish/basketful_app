import { useState, useEffect, useRef, useCallback } from 'react';
import {
  Alert,
  Box,
  Button,
  CircularProgress,
  Divider,
  FormControlLabel,
  Switch,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  TextField,
  Typography,
} from '@mui/material';
import { ProgramWindowRow } from './ProgramWindowRow';
import { API_URL } from '../../../../utils/apiUrl';
import type { OrderWindowDashboardData, OrderWindowSettings } from '../../types';

export const OrderWindowDashboard = ({
  globalSettings,
  onSaveGlobal,
  saving,
}: {
  globalSettings: OrderWindowSettings;
  onSaveGlobal: (settings: OrderWindowSettings) => void;
  saving: boolean;
}) => {
  const [global, setGlobal] = useState(globalSettings);
  const [dashboard, setDashboard] = useState<OrderWindowDashboardData | null>(null);
  const [dashLoading, setDashLoading] = useState(true);
  const [asOf, setAsOf] = useState<string | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const fetchDashboard = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/api/v1/order-windows/status/`, {
        credentials: 'include',
      });
      if (res.ok) {
        const data: OrderWindowDashboardData = await res.json();
        setDashboard(data);
        setAsOf(data.as_of);
      }
    } catch {
      // silent — stale data is still useful
    }
    setDashLoading(false);
  }, []);

  useEffect(() => {
    fetchDashboard();
    pollRef.current = setInterval(fetchDashboard, 30_000);
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [fetchDashboard]);

  const secondsAgo =
    asOf ? Math.round((Date.now() - new Date(asOf).getTime()) / 1000) : null;

  return (
    <Box>
      {/* Global defaults panel */}
      <Box sx={{ maxWidth: 560, mb: 4 }}>
        <Typography variant="h6" sx={{ mb: 2, fontSize: '0.95rem', fontWeight: 600 }}>
          Global Defaults
        </Typography>
        <Typography variant="body2" sx={{ color: 'text.secondary', mb: 2 }}>
          Programs without a custom override inherit these values.
        </Typography>
        <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap', alignItems: 'flex-start' }}>
          <TextField
            size="small"
            type="number"
            label="Opens (hrs before class)"
            value={global.hours_before_class}
            onChange={e =>
              setGlobal({ ...global, hours_before_class: parseInt(e.target.value) || 0 })
            }
            helperText="1–168 hours"
            sx={{ width: 200 }}
          />
          <TextField
            size="small"
            type="number"
            label="Closes (hrs before class)"
            value={global.hours_before_close}
            onChange={e =>
              setGlobal({ ...global, hours_before_close: parseInt(e.target.value) || 0 })
            }
            helperText="0 = closes at class time"
            sx={{ width: 200 }}
          />
          <FormControlLabel
            control={
              <Switch
                checked={global.enabled}
                onChange={e => setGlobal({ ...global, enabled: e.target.checked })}
              />
            }
            label="Enabled"
            sx={{ mt: 0.5 }}
          />
        </Box>
        <Button
          variant="contained"
          sx={{ mt: 2 }}
          onClick={() => onSaveGlobal(global)}
          disabled={saving}
        >
          Save Global Defaults
        </Button>
      </Box>

      <Divider sx={{ mb: 3 }} />

      {/* Live program status table */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
        <Typography variant="h6" sx={{ fontSize: '0.95rem', fontWeight: 600 }}>
          Live Program Status
        </Typography>
        <Typography variant="caption" sx={{ color: 'text.secondary' }}>
          {secondsAgo !== null ? `Updated ${secondsAgo}s ago` : ''}
          <Button size="small" sx={{ ml: 1 }} onClick={fetchDashboard}>
            ↻ Refresh
          </Button>
        </Typography>
      </Box>

      {dashLoading ? (
        <CircularProgress size={24} />
      ) : !dashboard || dashboard.programs.length === 0 ? (
        <Alert severity="info">No programs found.</Alert>
      ) : (
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>Program</TableCell>
              <TableCell>Schedule</TableCell>
              <TableCell>Status</TableCell>
              <TableCell>Changes In</TableCell>
              <TableCell align="center">Active Orders</TableCell>
              <TableCell />
            </TableRow>
          </TableHead>
          <TableBody>
            {dashboard.programs.map(p => (
              <ProgramWindowRow key={p.program_id} program={p} onRefresh={fetchDashboard} />
            ))}
          </TableBody>
        </Table>
      )}
    </Box>
  );
};
