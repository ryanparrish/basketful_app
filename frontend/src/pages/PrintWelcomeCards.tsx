/**
 * PrintWelcomeCards — bilingual welcome card print page
 *
 * Data source (priority order):
 * 1. location.state.participants    — fastest, zero network (first render after bulk-create)
 * 2. sessionStorage[bulk_batch_X]   — fast, survives F5 in the same tab
 * 3. GET /participants/bulk-create-batches/:batchId/  — always works (server recovery)
 */
import { useEffect, useRef, useState } from 'react';
import { useLocation, useNavigate, useParams } from 'react-router-dom';
import { Title } from 'react-admin';
import {
  Alert,
  Box,
  Button,
  CircularProgress,
  Typography,
} from '@mui/material';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import PrintIcon from '@mui/icons-material/Print';
import { API_URL } from '../utils/apiUrl';
import { useBlocker } from 'react-router-dom';

const PARTICIPANT_URL =
  (import.meta as unknown as { env: Record<string, string> }).env.VITE_PARTICIPANT_URL ??
  'https://app.basketful.org';

interface WelcomeParticipant {
  id: number;
  name: string;
  customer_number: string;
  email: string;
  preferred_language: 'en' | 'es';
  program_name: string;
}

const CARD_COPY = {
  en: {
    greeting: (name: string) => `Welcome, ${name}!`,
    loginLabel: 'YOUR LOGIN NUMBER',
    loginAt: 'Log in at:',
    instruction: 'Check your email to set your password',
  },
  es: {
    greeting: (name: string) => `¡Bienvenido/a, ${name}!`,
    loginLabel: 'SU NÚMERO DE ACCESO',
    loginAt: 'Ingrese en:',
    instruction: 'Revise su correo para crear su contraseña',
  },
};

const nameFontSize = (name: string): string => {
  if (name.length <= 20) return '16pt';
  if (name.length <= 32) return '13pt';
  return '11pt';
};

const truncate = (s: string, max = 40) =>
  s.length > max ? s.slice(0, max - 1) + '…' : s;

const WelcomeCard = ({ participant }: { participant: WelcomeParticipant }) => {
  const lang = participant.preferred_language ?? 'en';
  const copy = CARD_COPY[lang] ?? CARD_COPY.en;
  const displayName = truncate(participant.name);
  const isTruncated = participant.name.length > 40;

  return (
    <Box
      className="welcome-card"
      sx={{
        border: '2px solid #333',
        borderRadius: '8px',
        padding: '24px',
        fontFamily: "'Atkinson Hyperlegible', system-ui, sans-serif",
      }}
    >
      <Typography variant="caption" sx={{ color: 'text.secondary', display: 'block', mb: 1 }}>
        Love Your Neighbor Food Pantry
      </Typography>

      <Typography
        sx={{
          fontSize: nameFontSize(displayName),
          fontWeight: 700,
          mb: 1,
        }}
      >
        {isTruncated ? (
          <span title="Name was shortened to fit the card — edit the participant record to adjust">
            {displayName} ⚠️
          </span>
        ) : (
          copy.greeting(displayName)
        )}
      </Typography>

      <Typography variant="overline" sx={{ display: 'block', mt: 2, color: 'text.secondary' }}>
        {copy.loginLabel}
      </Typography>

      <Box
        className="customer-number-badge"
        aria-label={`Your login number: ${participant.customer_number}`}
        sx={{
          fontSize: { screen: '2rem', print: '36pt' },
          fontWeight: 900,
          fontFamily: "'Atkinson Hyperlegible', 'Courier New', monospace",
          letterSpacing: '0.12em',
          border: '3px solid #000',
          padding: '8px 16px',
          display: 'inline-block',
          my: 1,
          borderRadius: '4px',
          bgcolor: '#f5f5f5',
        }}
      >
        {participant.customer_number}
      </Box>

      <Typography variant="body2" sx={{ mt: 1.5 }}>
        {copy.loginAt}
      </Typography>
      <Typography variant="body1" sx={{ fontWeight: 600 }}>
        {PARTICIPANT_URL}/login
      </Typography>

      <Typography variant="body2" sx={{ mt: 1.5, color: 'text.secondary' }}>
        {copy.instruction}
      </Typography>
    </Box>
  );
};

const PrintWelcomeCards = () => {
  const { batchId } = useParams<{ batchId?: string }>();
  const location = useLocation();
  const navigate = useNavigate();
  const hasPrinted = useRef(false);

  const [participants, setParticipants] = useState<WelcomeParticipant[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Guard: warn before navigating away if not yet printed
  useBlocker(() =>
    !hasPrinted.current
      ? !window.confirm('Welcome cards have not been printed. Leave anyway?')
      : false
  );

  useEffect(() => {
    if (!hasPrinted.current && participants) {
      const handler = (e: BeforeUnloadEvent) => { e.preventDefault(); };
      window.addEventListener('beforeunload', handler);
      return () => window.removeEventListener('beforeunload', handler);
    }
  }, [participants]);

  // Three-layer fallback: location.state → sessionStorage → server
  useEffect(() => {
    // Layer 1: location.state
    const stateParticipants = (location.state as { participants?: WelcomeParticipant[] } | null)?.participants;
    if (stateParticipants?.length) {
      setParticipants(stateParticipants);
      return;
    }

    // Layer 2: sessionStorage
    if (batchId) {
      const cached = sessionStorage.getItem(`bulk_batch_${batchId}`);
      if (cached) {
        try {
          const parsed = JSON.parse(cached) as WelcomeParticipant[];
          if (parsed?.length) {
            setParticipants(parsed);
            return;
          }
        } catch {
          // Fall through to server fetch
        }
      }
    }

    // Layer 3: server fetch
    if (batchId && batchId !== 'single') {
      setLoading(true);
      fetch(`${API_URL}/participants/bulk-create-batches/${batchId}/`, { credentials: 'include' })
        .then(r => {
          if (!r.ok) throw new Error(`HTTP ${r.status}`);
          return r.json();
        })
        .then(data => {
          setParticipants(data.created ?? []);
        })
        .catch(e => setError(`Could not load participants: ${e.message}`))
        .finally(() => setLoading(false));
    } else if (batchId === 'single') {
      // Single-participant path
      const cached = sessionStorage.getItem('single_participant_card');
      if (cached) {
        try {
          setParticipants(JSON.parse(cached) as WelcomeParticipant[]);
        } catch {
          setError('Could not load participant data.');
        }
      }
    } else {
      setError('No participant data found.');
    }
  }, [batchId, location.state]);

  const handlePrint = () => {
    hasPrinted.current = true;
    if (batchId) sessionStorage.removeItem(`bulk_batch_${batchId}`);
    window.print();
  };

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', p: 6 }}>
        <CircularProgress />
      </Box>
    );
  }

  if (error) {
    return (
      <Box sx={{ p: 3 }}>
        <Alert severity="error">{error}</Alert>
        <Button startIcon={<ArrowBackIcon />} onClick={() => navigate('/participants')} sx={{ mt: 2 }}>
          Back to Participants
        </Button>
      </Box>
    );
  }

  if (!participants) return null;

  if (participants.length === 0) {
    return (
      <Box sx={{ p: 3 }}>
        <Alert severity="info">No participants to print cards for.</Alert>
        <Button startIcon={<ArrowBackIcon />} onClick={() => navigate('/participants')} sx={{ mt: 2 }}>
          Back to Participants
        </Button>
      </Box>
    );
  }

  return (
    <>
      <Title title="Print Welcome Cards" />

      {/* Screen-only toolbar — hidden at print */}
      <Box
        className="no-print"
        sx={{
          p: 2,
          display: 'flex',
          gap: 2,
          alignItems: 'center',
          borderBottom: 1,
          borderColor: 'divider',
          '@media print': { display: 'none' },
        }}
      >
        <Button
          startIcon={<ArrowBackIcon />}
          onClick={() => navigate('/participants')}
        >
          Back to Participants
        </Button>

        <Alert
          severity="warning"
          sx={{ flex: 1, py: 0 }}
        >
          ⚠️ Before printing: confirm the correct printer is selected in the print dialog. Welcome cards contain participant login numbers.
        </Alert>

        <Button
          variant="contained"
          startIcon={<PrintIcon />}
          onClick={handlePrint}
          autoFocus
          size="large"
        >
          Print Welcome Cards ({participants.length})
        </Button>
      </Box>

      {/* Card grid */}
      <Box
        className="card-grid"
        sx={{
          display: 'flex',
          flexDirection: 'column',
          gap: 2,
          p: 3,
          maxWidth: 480,
          '@media print': {
            display: 'grid',
            gridTemplateColumns: 'repeat(2, 1fr)',
            gap: '0.25in',
            padding: '0.5in',
            maxWidth: 'unset',
          },
        }}
      >
        {participants.map((p) => (
          <WelcomeCard key={p.id ?? p.customer_number} participant={p} />
        ))}
      </Box>

      {/* Print CSS */}
      <style>{`
        @media print {
          header, nav, aside,
          .RaSidebar-root, .RaAppBar-root, .no-print {
            display: none !important;
          }
          .welcome-card {
            break-inside: avoid;
            page-break-inside: avoid;
          }
          @page {
            margin: 0.75in;
            size: letter;
          }
        }
      `}</style>
    </>
  );
};

export default PrintWelcomeCards;
