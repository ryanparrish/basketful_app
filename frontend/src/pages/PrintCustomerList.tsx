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
import apiClient from '../lib/api/apiClient.ts';

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
    const fetchAll = async () => {
      try {
        const [brandingRes, participantRes] = await Promise.all([
          apiClient.get('/settings/branding-settings/current/'),
          apiClient.get(`/participants/?id__in=${ids.join(',')}&page_size=500`),
        ]);

        setBranding(brandingRes.data ?? null);

        // Support both paginated { results: [] } and plain array responses
        const pData = participantRes.data;
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
          /* Hide React-Admin layout elements */
          .no-print { display: none !important; }
          .RaLayout-appFrame { margin-left: 0 !important; }
          .RaSidebar-root, .RaAppBar-root, .RaLayout-sidebar, .MuiDrawer-root { 
            display: none !important; 
          }
          .RaLayout-content, .RaLayout-contentWithSidebar {
            margin-left: 0 !important;
            margin-top: 0 !important;
            padding: 0 !important;
          }
          
          /* Print-specific styles */
          body, html { 
            font-family: Arial, sans-serif; 
            font-size: 11pt; 
            margin: 0 !important;
            padding: 0 !important;
            color: #000;
          }
          #root, #root > div {
            margin: 0 !important;
            padding: 0 !important;
          }
          h1 { 
            font-size: 18pt; 
            font-weight: bold;
            margin: 0 0 0.25in;
            text-align: center;
          }
          h2 { 
            font-size: 14pt; 
            font-weight: bold;
            margin: 0.2in 0 0.1in; 
            border-bottom: 2px solid #333;
            padding-bottom: 4px;
          }
          table { 
            width: 100%; 
            border-collapse: collapse; 
            margin-bottom: 0.15in;
          }
          th, td { 
            border: 1px solid #666; 
            padding: 6px 10px; 
            text-align: left; 
            font-size: 10pt;
          }
          th { 
            background: #e8e8e8; 
            font-weight: bold;
            border: 1px solid #333;
          }
          .print-header { 
            display: flex; 
            align-items: center; 
            justify-content: center;
            gap: 16px; 
            margin-bottom: 0.3in;
            border-bottom: 3px solid #333;
            padding-bottom: 0.15in;
          }
          .print-header img { 
            max-height: 60px; 
          }
          .print-footer {
            margin-top: 0.3in;
            padding-top: 0.1in;
            border-top: 1px solid #666;
            font-size: 9pt;
            text-align: center;
            color: #666;
          }
          .print-content-wrapper {
            padding: 0.5in !important;
          }
          tbody tr:nth-child(odd) {
            background-color: #f9f9f9;
          }
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

      <Box className="print-content-wrapper" sx={{ p: 3 }}>
        {/* Branding header */}
        <div className="print-header">
          {branding?.logo && (
            <img src={branding.logo} alt={branding.organization_name ?? 'Logo'} />
          )}
          <Typography variant="h4" component="h1">
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
            <Box key={program} sx={{ mb: 4 }}>
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

        <div className="print-footer">
          <Typography variant="body2" component="div">
            Printed: {new Date().toLocaleString()} · Total: {selected.size} customer(s)
          </Typography>
        </div>
      </Box>
    </>
  );
};

export default PrintCustomerList;
