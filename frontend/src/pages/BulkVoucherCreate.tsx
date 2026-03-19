/**
 * Bulk Voucher Creation Page - Two-Step Flow
 * 
 * Step 1: Configuration (mode, program, voucher type, notes)
 * Step 2: Review & Select Participants
 */
import { useState } from 'react';
import {
  Title,
  useDataProvider,
  useNotify,
  useRedirect,
  useGetList,
  Loading,
} from 'react-admin';
import {
  Card,
  CardContent,
  CardHeader,
  Button,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  TextField,
  Checkbox,
  Alert,
  Box,
  Chip,
  Table,
  TableHead,
  TableRow,
  TableCell,
  TableBody,
  CircularProgress,
  Typography,
  Paper,
  Divider,
} from '@mui/material';

interface Program {
  id: number;
  name: string;
  participant_count: number;
}

interface Participant {
  id: number;
  name: string;
  email: string;
  customer_number: string;
  account_balance_id: number | null;
  has_account: boolean;
  active: boolean;
}

interface PreviewResponse {
  participants: Participant[];
  total_count: number;
}

export const BulkVoucherCreate = () => {
  const dataProvider = useDataProvider();
  const notify = useNotify();
  const redirect = useRedirect();

  // Step management
  const [step, setStep] = useState<1 | 2>(1);

  // Form state
  const [mode, setMode] = useState<'program' | 'select'>('program');
  const [selectedProgram, setSelectedProgram] = useState<number | ''>('');
  const [voucherType, setVoucherType] = useState<'grocery' | 'life'>('grocery');
  const [notes, setNotes] = useState('');
  
  // Step 2 state
  const [programParticipants, setProgramParticipants] = useState<Participant[]>([]);
  const [selectedParticipantIds, setSelectedParticipantIds] = useState<number[]>([]);
  const [loadingParticipants, setLoadingParticipants] = useState(false);
  
  // For select mode
  const [selectedAccounts, setSelectedAccounts] = useState<number[]>([]);
  
  // Submission state
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [result, setResult] = useState<{ created_count: number } | null>(null);

  // Fetch programs
  const { data: programs, isPending: programsLoading } = useGetList<Program>('programs', {
    pagination: { page: 1, perPage: 100 },
    sort: { field: 'name', order: 'ASC' },
  });

  // Fetch all participants for selection mode
  const { data: participants, isPending: participantsLoading } = useGetList<Participant>(
    'participants',
    {
      pagination: { page: 1, perPage: 500 },
      filter: { active: true },
      sort: { field: 'name', order: 'ASC' },
    }
  );

  // Load participants when program selected (for preview)
  const loadProgramParticipants = async (programId: number) => {
    setLoadingParticipants(true);
    try {
      const response = await fetch(
        `/api/v1/vouchers/bulk_create/preview/?program_id=${programId}`,
        {
          headers: {
            'Authorization': `Bearer ${localStorage.getItem('token')}`,
          },
        }
      );
      
      if (!response.ok) {
        throw new Error('Failed to load participants');
      }
      
      const data: PreviewResponse = await response.json();
      setProgramParticipants(data.participants);
      
      // Pre-select all participants with accounts by default
      const participantIds = data.participants
        .filter(p => p.has_account)
        .map(p => p.id);
      setSelectedParticipantIds(participantIds);
    } catch (error) {
      notify(`Error loading participants: ${error}`, { type: 'error' });
    }
    setLoadingParticipants(false);
  };

  const handleAccountToggle = (accountId: number) => {
    setSelectedAccounts((prev) =>
      prev.includes(accountId)
        ? prev.filter((id) => id !== accountId)
        : [...prev, accountId]
    );
  };

  const handleParticipantToggle = (participantId: number) => {
    setSelectedParticipantIds((prev) =>
      prev.includes(participantId)
        ? prev.filter((id) => id !== participantId)
        : [...prev, participantId]
    );
  };

  const handleSelectAll = () => {
    if (mode === 'program') {
      const allIds = programParticipants
        .filter(p => p.has_account)
        .map(p => p.id);
      setSelectedParticipantIds(allIds);
    } else if (participants) {
      const allIds = participants.map((p) => p.account_balance_id).filter(Boolean);
      setSelectedAccounts(allIds as number[]);
    }
  };

  const handleDeselectAll = () => {
    if (mode === 'program') {
      setSelectedParticipantIds([]);
    } else {
      setSelectedAccounts([]);
    }
  };

  const handleNextStep = async () => {
    if (mode === 'program' && selectedProgram) {
      await loadProgramParticipants(selectedProgram as number);
      setStep(2);
    } else if (mode === 'select' && selectedAccounts.length > 0) {
      setStep(2);
    } else {
      notify('Please select a program or at least one participant', {
        type: 'warning',
      });
    }
  };

  const handleBackStep = () => {
    setStep(1);
  };

  const handleSubmit = async () => {
    setIsSubmitting(true);
    setResult(null);

    try {
      const payload: {
        voucher_type: string;
        notes: string;
        program_id?: number;
        account_ids?: number[];
      } = {
        voucher_type: voucherType,
        notes,
      };

      if (mode === 'program' && selectedProgram) {
        payload.program_id = selectedProgram as number;
      } else if (mode === 'select' && selectedAccounts.length > 0) {
        payload.account_ids = selectedAccounts;
      } else {
        notify('Please select a program or at least one participant', {
          type: 'warning',
        });
        setIsSubmitting(false);
        return;
      }

      const response = await dataProvider.create('vouchers/bulk_create', {
        data: payload,
      });

      setResult(response.data as { created_count: number });
      notify(`Successfully created ${response.data.created_count} vouchers`, {
        type: 'success',
      });
    } catch (error) {
      notify(`Error creating vouchers: ${error}`, { type: 'error' });
    }

    setIsSubmitting(false);
  };

  if (programsLoading) return <Loading />;

  return (
    <div>
      <Title title="Bulk Voucher Creation" />

      <Card sx={{ maxWidth: 800, m: 2 }}>
        <CardHeader title="Create Vouchers in Bulk" />
        <CardContent>
          {/* Mode Selection */}
          <FormControl fullWidth sx={{ mb: 3 }}>
            <InputLabel>Creation Mode</InputLabel>
            <Select
              value={mode}
              onChange={(e) => setMode(e.target.value as 'program' | 'select')}
              label="Creation Mode"
            >
              <MenuItem value="program">By Program (All Active Participants)</MenuItem>
              <MenuItem value="select">Select Individual Participants</MenuItem>
            </Select>
          </FormControl>

          {/* Program Selection */}
          {mode === 'program' && (
            <FormControl fullWidth sx={{ mb: 3 }}>
              <InputLabel>Program</InputLabel>
              <Select
                value={selectedProgram}
                onChange={(e) => setSelectedProgram(e.target.value as number)}
                label="Program"
              >
                {(programs || []).map((program) => (
                  <MenuItem key={program.id} value={program.id}>
                    {program.name} ({program.participant_count} participants)
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
          )}

          {/* Participant Selection */}
          {mode === 'select' && (
            <Box sx={{ mb: 3 }}>
              <Box sx={{ mb: 2, display: 'flex', gap: 1 }}>
                <Button variant="outlined" size="small" onClick={handleSelectAll}>
                  Select All
                </Button>
                <Button variant="outlined" size="small" onClick={handleDeselectAll}>
                  Deselect All
                </Button>
                <Chip
                  label={`${selectedAccounts.length} selected`}
                  color="primary"
                />
              </Box>

              {participantsLoading ? (
                <CircularProgress />
              ) : (
                <Box
                  sx={{
                    maxHeight: 300,
                    overflow: 'auto',
                    border: '1px solid #ddd',
                    borderRadius: 1,
                  }}
                >
                  <Table size="small">
                    <TableHead>
                      <TableRow>
                        <TableCell padding="checkbox" />
                        <TableCell>Name</TableCell>
                        <TableCell>Customer #</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {(participants || []).map((participant) => (
                        <TableRow
                          key={participant.id}
                          hover
                          onClick={() =>
                            handleAccountToggle(participant.account_balance_id)
                          }
                          sx={{ cursor: 'pointer' }}
                        >
                          <TableCell padding="checkbox">
                            <Checkbox
                              checked={selectedAccounts.includes(
                                participant.account_balance_id
                              )}
                            />
                          </TableCell>
                          <TableCell>{participant.name}</TableCell>
                          <TableCell>{participant.customer_number}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </Box>
              )}
            </Box>
          )}

          {/* Voucher Type */}
          <FormControl fullWidth sx={{ mb: 3 }}>
            <InputLabel>Voucher Type</InputLabel>
            <Select
              value={voucherType}
              onChange={(e) => setVoucherType(e.target.value as 'grocery' | 'life')}
              label="Voucher Type"
            >
              <MenuItem value="grocery">Grocery</MenuItem>
              <MenuItem value="life">Life Skills</MenuItem>
            </Select>
          </FormControl>

          {/* Notes */}
          <TextField
            fullWidth
            multiline
            rows={3}
            label="Notes (optional)"
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            sx={{ mb: 3 }}
          />

          {/* Result Display */}
          {result && (
            <Alert severity="success" sx={{ mb: 3 }}>
              Successfully created {result.created_count} vouchers!
            </Alert>
          )}

          {/* Actions */}
          <Box sx={{ display: 'flex', gap: 2 }}>
            <Button
              variant="contained"
              color="primary"
              onClick={handleSubmit}
              disabled={isSubmitting}
            >
              {isSubmitting ? <CircularProgress size={24} /> : 'Create Vouchers'}
            </Button>
            <Button variant="outlined" onClick={() => redirect('/vouchers')}>
              Cancel
            </Button>
          </Box>
        </CardContent>
      </Card>
    </div>
  );
};

export default BulkVoucherCreate;
