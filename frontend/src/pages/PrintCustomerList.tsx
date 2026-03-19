/**
 * PrintCustomerList — print-optimized view of selected participants grouped by program.
 * Mirrors account/print_customer_list.html from the Django admin.
 * IDs are passed via query param: /participants/print-customer-list?ids=1,2,3
 */
import { useEffect, useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { Button, CircularProgress, Typography, Box, Checkbox, FormControlLabel } from '@mui/material';
import PrintIcon from '@mui/icons-material/Print';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import { API_URL } from '../utils/apiUrl';

interface Participant {
  id: number;
  name: string;
  customer_number: string;
  program_name: string;
}

interface BrandingSettings {
  organization_name: string;
  logo: string | null;
}

export const PrintCustomerList = () => {
  const navigate = useNavigate();
  const location = useLocation();

  const ids = new URLSearchParams(location.search)
    .get('ids')
    ?.split(',')
    .map((id) => id.trim())
    .filter(Boolean) ?? [];

  const [participants, setParticipants] = useState<Participant[]>([]);
  const [branding, setBranding] = useState<BrandingSettings | null>(null);
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const token = localStorage.getItem('accessToken');
    const headers = { Authorization: `Bearer ${token}` };

    const fetchAll = async () => {
      try {
        const [brandingRes, ...participantRes] = await Promise.all([
          fetch(`${API_URL}/api/v1/settings/branding-settings/current/`, { headers }),
          // Fetch each page of participants matching the IDs.
          // Using filter param ids=1,2,3 — falls back to fetching all then filtering client-side.
          fetch(
            `${API_URL}/api/v1/participants/?id__in=${ids.join(',')}&page_size=500`,
            { headers }
          ),
        ]);

        const brandingData = brandingRes.ok ? await brandingRes.json() : null;
        setBranding(brandingData);

        const pData = await participantRes[0].json();
        // Support both paginated { results: [] } and plain array responses
        const all: Participant[] = Array.isArray(pData) ? pData : (pData.results ?? []);
        // Filter to only the requested IDs (in case the backend doesn't support id__in)
        const idSet = new Set(ids.map(Number));
        const filtered = all.filter((p) => idSet.has(p.id));
        setParticipants(filtered);
        setSelected(new Set(filtered.map((p) => p.id)));
      } catch (e) {
        setError((e as Error).message);
      } finally {
        setIsLoading(false);
      }
    };

    if (ids.length === 0) {
      setIsLoading(false);
      return;
    }
    fetchAll();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Group by program
  const grouped: Record<string, Participant[]> = {};
  participants
    .filter((p) => selected.has(p.id))
    .forEach((p) => {
      const prog = p.program_name || 'No Program';
      if (!grouped[prog]) grouped[prog] = [];
      grouped[prog].push(p);
    });
  const programNames = Object.keys(grouped).sort();

  const toggleAll = () => {
    if (selected.size === participants.length) {
      setSelected(new Set());
    } else {
      setSelected(new Set(participants.map((p) => p.id)));
    }
  };

  const toggleOne = (id: number) => {
    const next = new Set(selected);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    setSelected(next);
  };

  if (isLoading)
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', p: 6 }}>
        <CircularProgress />
      </Box>
    );

  if (error)
    return (
      <Box sx={{ p: 4 }}>
        <Typography color="error">{error}</Typography>
      </Box>
    );

  if (ids.length === 0)
    return (
      <Box sx={{ p: 4 }}>
        <Typography>No participants selected.</Typography>
        <Button onClick={() => navigate('/participants')} startIcon={<ArrowBackIcon />} sx={{ mt: 2 }}>
          Back to Participants
        </Button>
      </Box>
    );

  return (
    <>
      <style>{`
        @media print {
          .no-print { display: none !important; }
          body { font-family: Arial, sans-serif; font-size: 12px; margin: 0; }
          h1 { font-size: 16px; margin: 0 0 8px; }
          h2 { font-size: 13px; margin: 16px 0 4px; }
          table { width: 100%; border-collapse: collapse; page-break-inside: avoid; }
          th, td { border: 1px solid #ccc; padding: 4px 8px; text-align: left; }
          th { background: #f0f0f0; }
          .print-header { display: flex; align-items: center; gap: 12px; margin-bottom: 16px; }
          .print-header img { max-height: 48px; }
        }
        @media screen {
          .print-header { display: flex; align-items: center; gap: 12px; margin-bottom: 16px; }
          .print-header img { max-height: 48px; }
        }
      `}</style>

      {/* Screen-only toolbar */}
      <Box
        className="no-print"
        sx={{ p: 2, display: 'flex', gap: 1, alignItems: 'center', borderBottom: '1px solid #e0e0e0', mb: 2 }}
      >
        <Button startIcon={<ArrowBackIcon />} onClick={() => navigate('/participants')}>
          Back
        </Button>
        <Button
          variant="contained"
          startIcon={<PrintIcon />}
          onClick={() => window.print()}
          disabled={selected.size === 0}
        >
          Print Selected ({selected.size})
        </Button>
        <FormControlLabel
          sx={{ ml: 2 }}
          control={
            <Checkbox
              checked={selected.size === participants.length && participants.length > 0}
              indeterminate={selected.size > 0 && selected.size < participants.length}
              onChange={toggleAll}
            />
          }
          label="Select All"
        />
      </Box>

      <Box sx={{ p: 3 }}>
        {/* Branding header */}
        <div className="print-header">
          {branding?.logo && (
            <img src={branding.logo} alt={branding.organization_name ?? 'Logo'} />
          )}
          <Typography variant="h5" component="h1">
            {branding?.organization_name ?? 'Customer List'}
          </Typography>
        </div>

        <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }} className="no-print">
          {selected.size} of {participants.length} participant(s) selected for printing.
        </Typography>

        {/* Programs + participants */}
        {programNames.length === 0 ? (
          <Typography color="text.secondary">No participants selected.</Typography>
        ) : (
          programNames.map((program) => (
            <Box key={program} sx={{ mb: 3 }}>
              <Typography variant="h6" component="h2" sx={{ mb: 1 }}>
                {program}
              </Typography>
              <table>
                <thead>
                  <tr>
                    <th className="no-print" style={{ width: 40 }}></th>
                    <th>Name</th>
                    <th>Customer #</th>
                  </tr>
                </thead>
                <tbody>
                  {grouped[program].map((p) => (
                    <tr key={p.id}>
                      <td className="no-print">
                        <Checkbox
                          size="small"
                          checked={selected.has(p.id)}
                          onChange={() => toggleOne(p.id)}
                        />
                      </td>
                      <td>{p.name}</td>
                      <td>{p.customer_number}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </Box>
          ))
        )}

        <Typography variant="body2" color="text.secondary" sx={{ mt: 3 }}>
          Printed: {new Date().toLocaleString()} · Total: {selected.size} customer(s)
        </Typography>
      </Box>
    </>
  );
};

export default PrintCustomerList;
