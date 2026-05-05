/**
 * BulkParticipantCreate — 4-step wizard for bulk participant intake
 *
 * Step 1: Data entry grid
 * Step 2: Validation preview (POST /bulk-validate)
 * Step 3: Confirm + create (POST /bulk-create)
 * Step 4: → navigates to PrintWelcomeCards
 */
import { useState, useEffect, useRef, useCallback } from 'react';
import {
  Box,
  Button,
  CircularProgress,
  IconButton,
  MenuItem,
  Paper,
  Select,
  Step,
  StepLabel,
  Stepper,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  TextField,
  Tooltip,
  Typography,
  Alert,
  Chip,
} from '@mui/material';
import GroupAddIcon from '@mui/icons-material/GroupAdd';
import DeleteOutlineIcon from '@mui/icons-material/DeleteOutline';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import { useNavigate } from 'react-router-dom';
import { Title, useNotify } from 'react-admin';
import { v4 as uuidv4 } from 'uuid';
import { API_URL } from '../utils/apiUrl';
import { useBlocker } from 'react-router-dom';

interface Program {
  id: number;
  name: string;
}

interface IntakeRow {
  id: string; // local UUID for React key
  name: string;
  email: string;
  program: number | '';
  adults: number;
  children: number;
  preferred_language: 'en' | 'es';
}

interface ValidationError {
  index: number;
  errors: Record<string, string[]>;
}

interface CreatedParticipant {
  id: number;
  name: string;
  email: string;
  customer_number: string;
  preferred_language: 'en' | 'es';
  program_name: string;
}

interface ResultRow {
  index: number;
  status: 'created' | 'failed';
  participant: CreatedParticipant | null;
  errors: Record<string, string[]> | null;
}

const STEPS = ['Enter Participants', 'Review', 'Confirm', 'Print Cards'];

const blankRow = (): IntakeRow => ({
  id: uuidv4(),
  name: '',
  email: '',
  program: '',
  adults: 1,
  children: 0,
  preferred_language: 'en',
});

const BulkParticipantCreate = () => {
  const navigate = useNavigate();
  const notify = useNotify();

  const [activeStep, setActiveStep] = useState(0);
  const [rows, setRows] = useState<IntakeRow[]>([blankRow()]);
  const [programs, setPrograms] = useState<Program[]>([]);
  const [validationErrors, setValidationErrors] = useState<ValidationError[]>([]);
  const [validating, setValidating] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [resultRows, setResultRows] = useState<ResultRow[]>([]);
  const [batchId, setBatchId] = useState<string | null>(null);
  const [emailGraceSeconds, setEmailGraceSeconds] = useState(0);
  const [graceCancelled, setGraceCancelled] = useState(false);
  const [countdown, setCountdown] = useState(0);
  const hasSubmitted = useRef(false);

  // Load programs on mount
  useEffect(() => {
    fetch(`${API_URL}/programs/?page_size=200`, { credentials: 'include' })
      .then(r => r.json())
      .then(data => setPrograms(Array.isArray(data) ? data : (data.results ?? [])))
      .catch(() => {});
  }, []);

  // Grace period countdown
  useEffect(() => {
    if (!emailGraceSeconds || graceCancelled) return;
    setCountdown(emailGraceSeconds);
    const interval = setInterval(() => {
      setCountdown(prev => {
        if (prev <= 1) {
          clearInterval(interval);
          return 0;
        }
        return prev - 1;
      });
    }, 1000);
    return () => clearInterval(interval);
  }, [emailGraceSeconds, graceCancelled]);

  // Warn on in-app navigation away from step 4 before printing
  useBlocker(() =>
    activeStep === 3 && !hasSubmitted.current
      ? !window.confirm('Welcome cards have not been printed. Leave anyway?')
      : false
  );

  // Warn on tab close / address-bar navigation
  useEffect(() => {
    if (activeStep !== 3) return;
    const handler = (e: BeforeUnloadEvent) => {
      if (!hasSubmitted.current) e.preventDefault();
    };
    window.addEventListener('beforeunload', handler);
    return () => window.removeEventListener('beforeunload', handler);
  }, [activeStep]);

  const updateRow = useCallback((id: string, field: keyof IntakeRow, value: unknown) => {
    setRows(prev => prev.map(r => r.id === id ? { ...r, [field]: value } : r));
  }, []);

  const addRow = () => setRows(prev => [...prev, blankRow()]);

  const clearRow = (id: string) => {
    setRows(prev => {
      if (prev.length === 1) return [blankRow()];
      return prev.filter(r => r.id !== id);
    });
  };

  const errorsForIndex = (index: number) =>
    validationErrors.find(e => e.index === index)?.errors ?? {};

  const serializeRows = () =>
    rows
      .filter(r => r.name.trim() || r.email.trim())
      .map(r => ({
        name: r.name,
        email: r.email,
        program: r.program !== '' ? r.program : null,
        adults: r.adults,
        children: r.children,
        preferred_language: r.preferred_language,
      }));

  const handleValidate = async () => {
    const payload = serializeRows();
    if (!payload.length) {
      notify('Add at least one participant row', { type: 'warning' });
      return;
    }
    setValidating(true);
    try {
      const res = await fetch(`${API_URL}/participants/bulk-validate/`, {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ participants: payload }),
      });
      const data = await res.json();
      if (!res.ok) {
        notify(data.detail ?? 'Validation failed', { type: 'error' });
        return;
      }
      setValidationErrors(data.errors ?? []);
      setActiveStep(1);
    } catch {
      notify('Network error during validation', { type: 'error' });
    } finally {
      setValidating(false);
    }
  };

  const handleCreate = async () => {
    if (submitting) return;
    setSubmitting(true);
    const payload = serializeRows();
    try {
      const res = await fetch(`${API_URL}/participants/bulk-create/`, {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ participants: payload }),
      });
      const data = await res.json();
      if (!res.ok) {
        notify(data.detail ?? 'Creation failed', { type: 'error' });
        setSubmitting(false);
        return;
      }
      setResultRows(data.rows ?? []);
      setBatchId(data.batch_id);
      setEmailGraceSeconds(data.email_grace_seconds ?? 0);
      setActiveStep(3);
    } catch {
      notify('Network error during creation', { type: 'error' });
      setSubmitting(false);
    }
  };

  const handleCancelEmails = async () => {
    if (!batchId) return;
    try {
      const res = await fetch(`${API_URL}/participants/bulk-create-batches/${batchId}/cancel/`, {
        method: 'POST',
        credentials: 'include',
      });
      if (res.ok) {
        setGraceCancelled(true);
        notify('Onboarding emails cancelled', { type: 'success' });
      }
    } catch {
      notify('Could not cancel emails', { type: 'error' });
    }
  };

  const handlePrint = () => {
    if (!batchId) return;
    const created = resultRows.filter(r => r.status === 'created').map(r => r.participant!);
    sessionStorage.setItem(`bulk_batch_${batchId}`, JSON.stringify(created));
    hasSubmitted.current = true;
    navigate(`/participants/welcome-cards/${batchId}`, {
      state: { participants: created, batchId },
      replace: true,
    });
  };

  const createdParticipants = resultRows.filter(r => r.status === 'created').map(r => r.participant!);
  const failedRows = resultRows.filter(r => r.status === 'failed');

  const fmtCountdown = (s: number) => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`;

  return (
    <Box sx={{ p: 3, maxWidth: 960, mx: 'auto' }}>
      <Title title="Bulk Create Participants" />
      <Typography variant="h5" gutterBottom sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
        <GroupAddIcon /> Bulk Create Participants
      </Typography>

      <Stepper activeStep={activeStep} sx={{ mb: 3 }}>
        {STEPS.map(label => (
          <Step key={label}><StepLabel>{label}</StepLabel></Step>
        ))}
      </Stepper>

      {/* ── Step 1: Data entry ─────────────────────────────────── */}
      {activeStep === 0 && (
        <Paper sx={{ p: 2 }}>
          {rows.length >= 50 && (
            <Alert severity="warning" sx={{ mb: 2 }}>
              You have {rows.length} rows. Maximum is 100 per batch.
            </Alert>
          )}
          <Box sx={{ overflowX: 'auto' }}>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>Name *</TableCell>
                  <TableCell>Email *</TableCell>
                  <TableCell>
                    Program *
                    <Tooltip title="Select the program shown on the participant's intake form. If you don't see the right program, ask your coordinator to add it in Settings → Programs.">
                      <span style={{ marginLeft: 4, cursor: 'help' }}>ℹ️</span>
                    </Tooltip>
                  </TableCell>
                  <TableCell>Adults</TableCell>
                  <TableCell>Children</TableCell>
                  <TableCell>Language</TableCell>
                  <TableCell />
                </TableRow>
              </TableHead>
              <TableBody>
                {rows.map((row) => (
                  <TableRow key={row.id}>
                    <TableCell>
                      <TextField
                        size="small"
                        value={row.name}
                        onChange={e => updateRow(row.id, 'name', e.target.value)}
                        placeholder="Full name"
                        sx={{ minWidth: 160 }}
                      />
                    </TableCell>
                    <TableCell>
                      <TextField
                        size="small"
                        type="email"
                        value={row.email}
                        onChange={e => updateRow(row.id, 'email', e.target.value)}
                        placeholder="email@example.com"
                        sx={{ minWidth: 200 }}
                      />
                    </TableCell>
                    <TableCell>
                      <Select
                        size="small"
                        value={row.program}
                        onChange={e => updateRow(row.id, 'program', e.target.value)}
                        displayEmpty
                        sx={{ minWidth: 160 }}
                      >
                        <MenuItem value=""><em>Select program</em></MenuItem>
                        {programs.map(p => (
                          <MenuItem key={p.id} value={p.id}>{p.name}</MenuItem>
                        ))}
                      </Select>
                    </TableCell>
                    <TableCell>
                      <TextField
                        size="small"
                        type="number"
                        value={row.adults}
                        onChange={e => updateRow(row.id, 'adults', Math.max(1, parseInt(e.target.value) || 1))}
                        inputProps={{ min: 1 }}
                        sx={{ width: 70 }}
                      />
                    </TableCell>
                    <TableCell>
                      <TextField
                        size="small"
                        type="number"
                        value={row.children}
                        onChange={e => updateRow(row.id, 'children', Math.max(0, parseInt(e.target.value) || 0))}
                        inputProps={{ min: 0 }}
                        sx={{ width: 70 }}
                      />
                    </TableCell>
                    <TableCell>
                      <Select
                        size="small"
                        value={row.preferred_language}
                        onChange={e => updateRow(row.id, 'preferred_language', e.target.value as 'en' | 'es')}
                      >
                        <MenuItem value="en">English</MenuItem>
                        <MenuItem value="es">Español</MenuItem>
                      </Select>
                    </TableCell>
                    <TableCell>
                      <Tooltip title="Clear row">
                        <IconButton size="small" onClick={() => clearRow(row.id)}>
                          <DeleteOutlineIcon fontSize="small" />
                        </IconButton>
                      </Tooltip>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </Box>

          <Box sx={{ mt: 2, display: 'flex', gap: 2 }}>
            <Button variant="outlined" onClick={addRow} disabled={rows.length >= 100}>
              + Add Another Person
            </Button>
            <Button
              variant="contained"
              onClick={handleValidate}
              disabled={validating}
              startIcon={validating ? <CircularProgress size={16} /> : undefined}
            >
              Review →
            </Button>
          </Box>
        </Paper>
      )}

      {/* ── Step 2: Validation preview ─────────────────────────── */}
      {activeStep === 1 && (
        <Paper sx={{ p: 2 }}>
          <Typography variant="h6" gutterBottom>
            Review Participants
          </Typography>
          {validationErrors.length === 0 ? (
            <Alert severity="success" sx={{ mb: 2 }}>
              All {serializeRows().length} rows are valid and ready to create.
            </Alert>
          ) : (
            <Alert severity="warning" sx={{ mb: 2 }}>
              {validationErrors.length} row(s) have errors. Fix them before confirming, or they will be skipped.
            </Alert>
          )}

          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>#</TableCell>
                <TableCell>Name</TableCell>
                <TableCell>Email</TableCell>
                <TableCell>Program</TableCell>
                <TableCell>Status</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {serializeRows().map((row, i) => {
                const errs = validationErrors.find(e => e.index === i)?.errors;
                const errMsgs = errs ? Object.values(errs).flat() : [];
                return (
                  <TableRow key={i}>
                    <TableCell>{i + 1}</TableCell>
                    <TableCell>{row.name}</TableCell>
                    <TableCell>{row.email}</TableCell>
                    <TableCell>
                      {programs.find(p => p.id === row.program)?.name ?? '—'}
                    </TableCell>
                    <TableCell>
                      {errMsgs.length === 0 ? (
                        <Chip label="✓ Ready" color="success" size="small" />
                      ) : (
                        <Tooltip title={errMsgs.join(' | ')}>
                          <Chip label="⚠ Error" color="warning" size="small" />
                        </Tooltip>
                      )}
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>

          <Box sx={{ mt: 2, display: 'flex', gap: 2 }}>
            <Button startIcon={<ArrowBackIcon />} onClick={() => setActiveStep(0)}>
              Back to edit
            </Button>
            <Button
              variant="contained"
              onClick={() => setActiveStep(2)}
            >
              Continue →
            </Button>
          </Box>
        </Paper>
      )}

      {/* ── Step 3: Confirm ────────────────────────────────────── */}
      {activeStep === 2 && (
        <Paper sx={{ p: 2 }}>
          <Typography variant="h6" gutterBottom>
            Confirm Creation
          </Typography>
          <Alert severity="info" sx={{ mb: 2 }}>
            You are about to create <strong>{serializeRows().length}</strong> participants.
            Each will receive an onboarding email with their login number and a link to set their password.
          </Alert>

          <Table size="small" sx={{ mb: 2 }}>
            <TableHead>
              <TableRow>
                <TableCell>Name</TableCell>
                <TableCell>Email</TableCell>
                <TableCell>Language</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {serializeRows().map((row, i) => (
                <TableRow key={i}>
                  <TableCell>{row.name}</TableCell>
                  <TableCell>{row.email}</TableCell>
                  <TableCell>{row.preferred_language === 'es' ? 'Español' : 'English'}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>

          <Box sx={{ display: 'flex', gap: 2 }}>
            <Button startIcon={<ArrowBackIcon />} onClick={() => setActiveStep(1)}>
              Back
            </Button>
            <Button
              variant="contained"
              color="primary"
              size="large"
              onClick={handleCreate}
              disabled={submitting}
              startIcon={submitting ? <CircularProgress size={18} /> : undefined}
            >
              {submitting ? 'Creating…' : `Create ${serializeRows().length} Participants`}
            </Button>
          </Box>
        </Paper>
      )}

      {/* ── Step 4: Print cards ────────────────────────────────── */}
      {activeStep === 3 && (
        <Paper sx={{ p: 2 }}>
          {emailGraceSeconds > 0 && !graceCancelled && countdown > 0 && (
            <Alert
              severity="warning"
              action={
                <Button color="inherit" size="small" onClick={handleCancelEmails}>
                  Cancel Emails
                </Button>
              }
              sx={{ mb: 2 }}
            >
              Onboarding emails send in <strong>{fmtCountdown(countdown)}</strong>
            </Alert>
          )}
          {graceCancelled && (
            <Alert severity="success" sx={{ mb: 2 }}>Onboarding emails cancelled.</Alert>
          )}

          <Alert severity="success" sx={{ mb: 2 }}>
            Created <strong>{createdParticipants.length}</strong> participants successfully.
            {failedRows.length > 0 && (
              <> <strong>{failedRows.length}</strong> could not be created (see below).</>
            )}
          </Alert>

          <Button
            variant="contained"
            size="large"
            onClick={handlePrint}
            autoFocus
            sx={{ mb: 3 }}
          >
            🖨 Print Welcome Cards ({createdParticipants.length})
          </Button>

          {failedRows.length > 0 && (
            <Box sx={{ mt: 2 }}>
              <Typography variant="subtitle1" color="error" gutterBottom>
                Could not create ({failedRows.length}):
              </Typography>
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>Row</TableCell>
                    <TableCell>Errors</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {failedRows.map(r => (
                    <TableRow key={r.index}>
                      <TableCell>#{r.index + 1} — {serializeRows()[r.index]?.name}</TableCell>
                      <TableCell>
                        {Object.entries(r.errors ?? {}).map(([field, msgs]) => (
                          <Box key={field}><strong>{field}:</strong> {(msgs as string[]).join(', ')}</Box>
                        ))}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </Box>
          )}
        </Paper>
      )}
    </Box>
  );
};

export default BulkParticipantCreate;
