/**
 * Bulk Voucher Creation Page
 * 
 * Allows creating vouchers for multiple participants at once,
 * either by selecting a program or individual accounts.
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
} from '@mui/material';

interface Program {
  id: number;
  name: string;
  participant_count: number;
}

interface Participant {
  id: number;
  name: string;
  customer_number: string;
  account_balance_id: number;
  active: boolean;
}

export const BulkVoucherCreate = () => {
  const dataProvider = useDataProvider();
  const notify = useNotify();
  const redirect = useRedirect();

  // Form state
  const [mode, setMode] = useState<'program' | 'select'>('program');
  const [selectedProgram, setSelectedProgram] = useState<number | ''>('');
  const [selectedAccounts, setSelectedAccounts] = useState<number[]>([]);
  const [voucherType, setVoucherType] = useState<'grocery' | 'life'>('grocery');
  const [notes, setNotes] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [result, setResult] = useState<{ created_count: number } | null>(null);

  // Fetch programs
  const { data: programs, isPending: programsLoading } = useGetList<Program>('programs', {
    pagination: { page: 1, perPage: 100 },
    sort: { field: 'name', order: 'ASC' },
  });

  // Fetch participants for selection mode
  const { data: participants, isPending: participantsLoading } = useGetList<Participant>(
    'participants',
    {
      pagination: { page: 1, perPage: 500 },
      filter: { active: true },
      sort: { field: 'name', order: 'ASC' },
    }
  );

  const handleAccountToggle = (accountId: number) => {
    setSelectedAccounts((prev) =>
      prev.includes(accountId)
        ? prev.filter((id) => id !== accountId)
        : [...prev, accountId]
    );
  };

  const handleSelectAll = () => {
    if (participants) {
      const allIds = participants.map((p) => p.account_balance_id).filter(Boolean);
      setSelectedAccounts(allIds as number[]);
    }
  };

  const handleDeselectAll = () => {
    setSelectedAccounts([]);
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
