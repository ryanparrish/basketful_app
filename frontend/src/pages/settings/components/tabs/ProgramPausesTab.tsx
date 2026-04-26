import { useState, useEffect } from 'react';
import { useNotify } from 'react-admin';
import {
  Alert,
  AlertTitle,
  Box,
  Button,
  Chip,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Divider,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  TextField,
  Typography,
} from '@mui/material';
import { API_URL } from '../../../../utils/apiUrl';
import { useDebounce } from '../../../../utils/useDebounce';
import type { ProgramPause, PauseFormData } from '../../types';

export const ProgramPausesTab = () => {
  const notify = useNotify();
  const [pauses, setPauses] = useState<ProgramPause[]>([]);
  const [activePause, setActivePause] = useState<ProgramPause | null>(null);
  const [pauseForm, setPauseForm] = useState<PauseFormData>({
    id: null,
    reason: '',
    pause_start: '',
    pause_end: '',
  });
  const [pauseModalOpen, setPauseModalOpen] = useState(false);
  const [pauseFormError, setPauseFormError] = useState<string | null>(null);
  const [overlapError, setOverlapError] = useState<string | null>(null);
  const [pauseSaving, setPauseSaving] = useState(false);
  const [pausesLoading, setPausesLoading] = useState(false);
  const [resyncingPause, setResyncingPause] = useState<number | null>(null);

  const debouncedPauseStart = useDebounce(pauseForm.pause_start, 500);
  const debouncedPauseEnd = useDebounce(pauseForm.pause_end, 500);

  const fetchPauses = () => {
    setPausesLoading(true);
    const token = localStorage.getItem('accessToken');
    Promise.all([
      fetch(`${API_URL}/api/v1/program-pauses/?ordering=-pause_start`, {
        headers: { Authorization: `Bearer ${token}` },
      }).then(r => (r.ok ? r.json() : { results: [] })),
      fetch(`${API_URL}/api/v1/program-pauses/active/`, {
        headers: { Authorization: `Bearer ${token}` },
      }).then(r => (r.ok ? r.json() : [])),
    ])
      .then(([allData, activeData]) => {
        setPauses(allData.results || []);
        setActivePause(activeData.length > 0 ? activeData[0] : null);
        setPausesLoading(false);
      })
      .catch(() => setPausesLoading(false));
  };

  useEffect(() => {
    fetchPauses();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!debouncedPauseStart || !debouncedPauseEnd) {
      setOverlapError(null);
      return;
    }
    const token = localStorage.getItem('accessToken');
    const params = new URLSearchParams({
      pause_start: debouncedPauseStart,
      pause_end: debouncedPauseEnd,
    });
    if (pauseForm.id) params.append('exclude_id', String(pauseForm.id));
    fetch(`${API_URL}/api/v1/program-pauses/check_overlap/?${params}`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then(r => (r.ok ? r.json() : null))
      .then(data => {
        if (data?.overlaps) {
          const c = data.conflicting;
          setOverlapError(
            `Overlaps with: "${c.reason || 'Unnamed'}" (${new Date(c.pause_start).toLocaleDateString()} – ${new Date(c.pause_end).toLocaleDateString()})`,
          );
        } else {
          setOverlapError(null);
        }
      })
      .catch(() => setOverlapError(null));
  }, [debouncedPauseStart, debouncedPauseEnd, pauseForm.id]);

  const validatePauseForm = (): string | null => {
    const now = new Date();
    const start = new Date(pauseForm.pause_start);
    const end = new Date(pauseForm.pause_end);
    if (!pauseForm.pause_start || !pauseForm.pause_end) return 'Start and end dates are required.';
    if (isNaN(start.getTime()) || isNaN(end.getTime())) return 'Invalid date format.';
    if (end <= start) return 'End date must be after start date.';
    const minStart = new Date(now.getTime() + 11 * 24 * 60 * 60 * 1000);
    if (start < minStart) return 'Pause must start at least 11 days from today.';
    const durationDays = (end.getTime() - start.getTime()) / (1000 * 60 * 60 * 24);
    if (durationDays > 14) return 'Pause cannot be longer than 14 days.';
    return null;
  };

  const openCreateModal = () => {
    setPauseForm({ id: null, reason: '', pause_start: '', pause_end: '' });
    setPauseFormError(null);
    setOverlapError(null);
    setPauseModalOpen(true);
  };

  const openEditModal = (pause: ProgramPause) => {
    const toLocal = (iso: string) => (iso ? iso.slice(0, 16) : '');
    setPauseForm({
      id: pause.id,
      reason: pause.reason || '',
      pause_start: toLocal(pause.pause_start),
      pause_end: toLocal(pause.pause_end),
    });
    setPauseFormError(null);
    setOverlapError(null);
    setPauseModalOpen(true);
  };

  const savePause = async () => {
    const err = validatePauseForm();
    if (err) { setPauseFormError(err); return; }
    if (overlapError) { setPauseFormError('Resolve the overlap conflict before saving.'); return; }
    setPauseSaving(true);
    const token = localStorage.getItem('accessToken');
    const url = pauseForm.id
      ? `${API_URL}/api/v1/program-pauses/${pauseForm.id}/`
      : `${API_URL}/api/v1/program-pauses/`;
    const method = pauseForm.id ? 'PATCH' : 'POST';
    try {
      const res = await fetch(url, {
        method,
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({
          reason: pauseForm.reason || null,
          pause_start: pauseForm.pause_start,
          pause_end: pauseForm.pause_end,
        }),
      });
      if (!res.ok) {
        const data = await res.json();
        const msg = (Object.values(data) as string[][]).flat().join(' ');
        setPauseFormError(msg || 'Error saving pause.');
      } else {
        notify(pauseForm.id ? 'Pause updated.' : 'Pause created.', { type: 'success' });
        setPauseModalOpen(false);
        fetchPauses();
      }
    } catch {
      setPauseFormError('Network error saving pause.');
    }
    setPauseSaving(false);
  };

  const archivePause = async (id: number) => {
    const token = localStorage.getItem('accessToken');
    try {
      const res = await fetch(`${API_URL}/api/v1/program-pauses/${id}/archive/`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        notify('Pause archived and vouchers cleaned up.', { type: 'success' });
        fetchPauses();
      } else {
        notify('Error archiving pause.', { type: 'error' });
      }
    } catch {
      notify('Error archiving pause.', { type: 'error' });
    }
  };

  const unarchivePause = async (id: number) => {
    const token = localStorage.getItem('accessToken');
    try {
      const res = await fetch(`${API_URL}/api/v1/program-pauses/${id}/unarchive/`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        notify('Pause unarchived.', { type: 'success' });
        fetchPauses();
      } else {
        notify('Error unarchiving pause.', { type: 'error' });
      }
    } catch {
      notify('Error unarchiving pause.', { type: 'error' });
    }
  };

  const resyncPause = async (id: number) => {
    setResyncingPause(id);
    const token = localStorage.getItem('accessToken');
    try {
      const res = await fetch(`${API_URL}/api/v1/program-pauses/${id}/resync/`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
      });
      const data = await res.json();
      if (res.ok) {
        notify(
          `Resync complete: ${data.updated_count} vouchers updated, ${data.skipped_count} already correct.`,
          { type: 'success' },
        );
        setPauses(prev => prev.map(p => (p.id === id ? data : p)));
        if (activePause?.id === id) setActivePause(data);
      } else {
        notify(data.detail || 'Error resyncing pause.', { type: 'error' });
      }
    } catch {
      notify('Error resyncing pause.', { type: 'error' });
    }
    setResyncingPause(null);
  };

  return (
    <Box sx={{ maxWidth: 860 }}>
      {activePause && (
        <Alert severity="warning" sx={{ mb: 3 }}>
          <AlertTitle>Pause Is Active</AlertTitle>
          {activePause.reason} — This Pause Is Active
        </Alert>
      )}

      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
        <Typography variant="h6">Program Pauses</Typography>
        <Button variant="contained" onClick={openCreateModal}>
          + Create Pause
        </Button>
      </Box>

      <Divider sx={{ mb: 2 }} />

      {pausesLoading ? (
        <CircularProgress />
      ) : pauses.length === 0 ? (
        <Alert severity="info">No program pauses found.</Alert>
      ) : (
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>Reason</TableCell>
              <TableCell>Start</TableCell>
              <TableCell>End</TableCell>
              <TableCell>Multiplier</TableCell>
              <TableCell>Status</TableCell>
              <TableCell align="right">Actions</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {pauses.map(pause => (
              <TableRow key={pause.id}>
                <TableCell>{pause.reason || '—'}</TableCell>
                <TableCell>{new Date(pause.pause_start).toLocaleString()}</TableCell>
                <TableCell>{new Date(pause.pause_end).toLocaleString()}</TableCell>
                <TableCell>{pause.multiplier}×</TableCell>
                <TableCell>
                  {pause.archived ? (
                    <Chip label="🗄️ Archived" size="small" variant="outlined" />
                  ) : pause.is_active ? (
                    <Chip label="Active" size="small" color="warning" />
                  ) : (
                    <Chip label="Upcoming" size="small" color="info" />
                  )}
                </TableCell>
                <TableCell align="right">
                  <Box sx={{ display: 'flex', gap: 1, justifyContent: 'flex-end' }}>
                    {!pause.archived && (
                      <Button
                        size="small"
                        variant="outlined"
                        onClick={() => openEditModal(pause)}
                      >
                        Edit
                      </Button>
                    )}
                    {pause.is_active && !pause.archived && (
                      <Button
                        size="small"
                        color="error"
                        variant="outlined"
                        onClick={() => resyncPause(pause.id)}
                        disabled={resyncingPause === pause.id}
                        title={
                          pause.last_resync_at
                            ? `Last resync: ${new Date(pause.last_resync_at).toLocaleString()} by ${pause.last_resync_by_username}`
                            : 'Never resynced — auto-trigger may not have fired'
                        }
                      >
                        {resyncingPause === pause.id ? (
                          <CircularProgress size={16} />
                        ) : (
                          'Resync'
                        )}
                      </Button>
                    )}
                    {pause.archived ? (
                      <Button
                        size="small"
                        color="secondary"
                        onClick={() => unarchivePause(pause.id)}
                      >
                        Unarchive
                      </Button>
                    ) : (
                      <Button
                        size="small"
                        color="warning"
                        onClick={() => archivePause(pause.id)}
                      >
                        Archive
                      </Button>
                    )}
                  </Box>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}

      <Dialog
        open={pauseModalOpen}
        onClose={() => setPauseModalOpen(false)}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle>{pauseForm.id ? 'Edit Pause' : 'Create Pause'}</DialogTitle>
        <DialogContent>
          <Box sx={{ pt: 1, display: 'flex', flexDirection: 'column', gap: 2 }}>
            <Alert severity="info" sx={{ fontSize: '0.8rem' }}>
              Pause must start ≥11 days from today · max 14 days duration · only one pause at a
              time
            </Alert>
            <TextField
              fullWidth
              label="Reason"
              value={pauseForm.reason}
              onChange={e => setPauseForm({ ...pauseForm, reason: e.target.value })}
              placeholder="e.g. Holiday break"
            />
            <TextField
              fullWidth
              label="Pause Start"
              type="datetime-local"
              value={pauseForm.pause_start}
              onChange={e => setPauseForm({ ...pauseForm, pause_start: e.target.value })}
              InputLabelProps={{ shrink: true }}
            />
            <TextField
              fullWidth
              label="Pause End"
              type="datetime-local"
              value={pauseForm.pause_end}
              onChange={e => setPauseForm({ ...pauseForm, pause_end: e.target.value })}
              InputLabelProps={{ shrink: true }}
            />
            {overlapError && <Alert severity="error">{overlapError}</Alert>}
            {pauseFormError && <Alert severity="error">{pauseFormError}</Alert>}
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setPauseModalOpen(false)}>Cancel</Button>
          <Button
            variant="contained"
            onClick={savePause}
            disabled={pauseSaving || !!overlapError}
          >
            {pauseSaving ? (
              <CircularProgress size={20} />
            ) : pauseForm.id ? (
              'Save Changes'
            ) : (
              'Create Pause'
            )}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};
