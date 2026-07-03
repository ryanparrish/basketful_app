/**
 * Voucher Creation Page - Flexible Flow
 * 
 * Supports:
 * - Creating vouchers for everyone in a program
 * - Creating vouchers for specific selected participants
 * 
 * Can be initialized with URL param ?mode=select for quick single-participant flow
 */
import { useState, useEffect } from 'react';
import {
  Title,
  useNotify,
  useRedirect,
  useGetList,
  Loading,
} from 'react-admin';
import { useSearchParams } from 'react-router-dom';
import apiClient from '../lib/api/apiClient.ts';
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
  Autocomplete,
  IconButton,
  Stack,
} from '@mui/material';
import CloseIcon from '@mui/icons-material/Close';

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
  const notify = useNotify();
  const redirect = useRedirect();
  const [searchParams] = useSearchParams();

  // Step management
  const [step, setStep] = useState<1 | 2>(1);

  // Form state - check URL params for initial mode
  const initialMode = (searchParams.get('mode') === 'select' ? 'select' : 'program') as 'program' | 'select';
  const [mode, setMode] = useState<'program' | 'select'>(initialMode);
  const [selectedProgram, setSelectedProgram] = useState<number | ''>('');
  const [voucherType, setVoucherType] = useState<'grocery' | 'life'>('grocery');
  const [quantity, setQuantity] = useState<number>(1);
  const [notes, setNotes] = useState('');
  
  // Step 2 state
  const [programParticipants, setProgramParticipants] = useState<Participant[]>([]);
  const [selectedParticipantIds, setSelectedParticipantIds] = useState<number[]>([]);
  const [loadingParticipants, setLoadingParticipants] = useState(false);
  
  // For select mode - store full participant objects for display
  const [selectedParticipants, setSelectedParticipants] = useState<Participant[]>([]);
  
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
      const response = await apiClient.get(
        `/vouchers/bulk_create/preview/?program_id=${programId}`
      );
      
      const data: PreviewResponse = response.data;
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

  const handleAddParticipant = (participant: Participant | null) => {
    if (!participant || !participant.account_balance_id) return;
    
    // Check if already selected
    if (selectedParticipants.some(p => p.id === participant.id)) {
      notify('Participant already selected', { type: 'info' });
      return;
    }
    
    setSelectedParticipants((prev) => [...prev, participant]);
  };

  const handleRemoveParticipant = (participantId: number) => {
    setSelectedParticipants((prev) => prev.filter((p) => p.id !== participantId));
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
      const eligible = participants.filter(p => p.account_balance_id !== null);
      setSelectedParticipants(eligible);
    }
  };

  const handleDeselectAll = () => {
    if (mode === 'program') {
      setSelectedParticipantIds([]);
    } else {
      setSelectedParticipants([]);
    }
  };

  const handleNextStep = async () => {
    if (mode === 'program' && selectedProgram) {
      await loadProgramParticipants(selectedProgram as number);
      setStep(2);
    } else if (mode === 'select' && selectedParticipants.length > 0) {
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
        quantity: number;
        notes: string;
        program_id?: number;
        participant_ids?: number[];
        account_ids?: number[];
      } = {
        voucher_type: voucherType,
        quantity,
        notes,
      };

      if (mode === 'program' && selectedProgram) {
        payload.program_id = selectedProgram as number;
        payload.participant_ids = selectedParticipantIds;
      } else if (mode === 'select' && selectedParticipants.length > 0) {
        payload.account_ids = selectedParticipants.map(p => p.account_balance_id!).filter(Boolean);
      } else {
        notify('Please select at least one participant', {
          type: 'warning',
        });
        setIsSubmitting(false);
        return;
      }

      const response = await apiClient.post('/vouchers/bulk_create/', payload);

      setResult(response.data as { created_count: number });
      notify(`Successfully created ${response.data.created_count} vouchers`, {
        type: 'success',
      });
      
      // Redirect after success
      setTimeout(() => redirect('/vouchers'), 2000);
    } catch (error) {
      notify(`Error creating vouchers: ${error}`, { type: 'error' });
    }

    setIsSubmitting(false);
  };

  if (programsLoading) return <Loading />;

  const selectedProgramData = programs?.find(p => p.id === selectedProgram);
  const participantsWithoutAccount = programParticipants.filter(p => !p.has_account);

  return (
    <div>
      <Title title="Create Vouchers" />

      <Card sx={{ maxWidth: 900, m: 2 }}>
        <CardHeader 
          title="Create Vouchers" 
          subheader={`Step ${step} of 2: ${step === 1 ? 'Configuration' : 'Review & Confirm'}`}
        />
        <CardContent>
          {/* Step 1: Configuration */}
          {step === 1 && (
            <>
              {/* Mode Selection */}
              <FormControl fullWidth sx={{ mb: 3 }}>
                <InputLabel>Who should receive these vouchers?</InputLabel>
                <Select
                  value={mode}
                  onChange={(e) => setMode(e.target.value as 'program' | 'select')}
                  label="Who should receive these vouchers?"
                >
                  <MenuItem value="program">Everyone in a Program</MenuItem>
                  <MenuItem value="select">Specific Participants</MenuItem>
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

              {/* Participant Selection - Autocomplete Style */}
              {mode === 'select' && (
                <Box sx={{ mb: 3 }}>
                  <Typography variant="subtitle2" sx={{ mb: 1, fontWeight: 'bold' }}>
                    Search and select participants:
                  </Typography>
                  
                  {participantsLoading ? (
                    <CircularProgress size={24} />
                  ) : (
                    <>
                      <Autocomplete
                        options={participants?.filter(p => p.account_balance_id !== null) || []}
                        getOptionLabel={(option) => `${option.name} (${option.customer_number})`}
                        renderInput={(params) => (
                          <TextField
                            {...params}
                            label="Search by name or customer number"
                            placeholder="Type to search, click to add..."
                            helperText="Search for a participant and click their name to add them to your selection"
                          />
                        )}
                        onChange={(_, value) => handleAddParticipant(value)}
                        value={null}
                        isOptionEqualToValue={(option, value) => option.id === value.id}
                        filterOptions={(options, { inputValue }) => {
                          const filtered = options.filter(option => 
                            option.name.toLowerCase().includes(inputValue.toLowerCase()) ||
                            option.customer_number?.toLowerCase().includes(inputValue.toLowerCase())
                          );
                          return filtered;
                        }}
                      />

                      {/* Selected Participants List - Always show */}
                      <Box sx={{ mt: 2 }}>
                        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
                          <Typography variant="subtitle2" fontWeight="bold">
                            Selected Participants ({selectedParticipants.length}):
                          </Typography>
                          {selectedParticipants.length > 0 && (
                            <Button 
                              size="small" 
                              onClick={handleDeselectAll}
                              variant="text"
                            >
                              Clear All
                            </Button>
                          )}
                        </Box>
                        {selectedParticipants.length === 0 ? (
                          <Paper 
                            variant="outlined" 
                            sx={{ 
                              p: 3, 
                              textAlign: 'center', 
                              bgcolor: '#f9f9f9',
                              border: '2px dashed #ddd'
                            }}
                          >
                            <Typography variant="body2" color="text.secondary">
                              No participants selected yet.<br/>
                              Search above and click on a participant to add them here.
                            </Typography>
                          </Paper>
                        ) : (
                          <Stack spacing={1}>
                            {selectedParticipants.map((participant) => (
                              <Chip
                                key={participant.id}
                                label={`${participant.name} (${participant.customer_number})`}
                                onDelete={() => handleRemoveParticipant(participant.id)}
                                deleteIcon={<CloseIcon />}
                                sx={{ justifyContent: 'space-between', px: 1 }}
                              />
                            ))}
                          </Stack>
                        )}
                      </Box>
                    </>
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

          {/* Quantity */}
          <TextField
            fullWidth
            type="number"
            label="Vouchers per Participant"
            value={quantity}
            onChange={(e) => setQuantity(Math.max(1, Math.min(10, parseInt(e.target.value) || 1)))}
            inputProps={{ min: 1, max: 10 }}
            helperText="Number of vouchers to create for each participant (1-10)"
            sx={{ mb: 3 }}
          />

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

          {/* Actions */}
          <Box sx={{ display: 'flex', gap: 2 }}>
            <Button
              variant="contained"
              color="primary"
              onClick={handleNextStep}
              disabled={
                (mode === 'program' && !selectedProgram) ||
                (mode === 'select' && selectedParticipants.length === 0)
              }
            >
              Next: Review & Confirm
            </Button>
            <Button variant="outlined" onClick={() => redirect('/vouchers')}>
              Cancel
            </Button>
          </Box>
            </>
          )}

          {/* Step 2: Review & Select */}
          {step === 2 && (
            <>
              {/* Configuration Summary */}
              <Paper elevation={0} sx={{ p: 2, mb: 3, bgcolor: '#f5f5f5' }}>
                <Typography variant="h6" gutterBottom>
                  Configuration Summary
                </Typography>
                <Divider sx={{ mb: 2 }} />
                {mode === 'program' && selectedProgramData && (
                  <Typography variant="body2">
                    <strong>Program:</strong> {selectedProgramData.name}
                  </Typography>
                )}
                <Typography variant="body2">
                  <strong>Voucher Type:</strong> {voucherType === 'grocery' ? 'Grocery' : 'Life Skills'}
                </Typography>
                <Typography variant="body2">
                  <strong>Quantity:</strong> {quantity} voucher{quantity > 1 ? 's' : ''} per participant
                </Typography>
                {notes && (
                  <Typography variant="body2">
                    <strong>Notes:</strong> {notes}
                  </Typography>
                )}
              </Paper>

              {/* Warnings */}
              {participantsWithoutAccount.length > 0 && (
                <Alert severity="warning" sx={{ mb: 3 }}>
                  <strong>Warning:</strong> {participantsWithoutAccount.length} participant(s) do not have an account balance and will be skipped.
                </Alert>
              )}

              {selectedParticipantIds.length === 0 && mode === 'program' && (
                <Alert severity="error" sx={{ mb: 3 }}>
                  <strong>Error:</strong> No participants selected. Please select at least one participant.
                </Alert>
              )}

              {/* Participant Selection */}
              {mode === 'program' && (
                <Box sx={{ mb: 3 }}>
                  <Box sx={{ mb: 2, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <Typography variant="h6">
                      Select Participants ({selectedParticipantIds.length} of {programParticipants.filter(p => p.has_account).length} selected)
                    </Typography>
                    <Box sx={{ display: 'flex', gap: 1 }}>
                      <Button variant="outlined" size="small" onClick={handleSelectAll}>
                        Select All
                      </Button>
                      <Button variant="outlined" size="small" onClick={handleDeselectAll}>
                        Deselect All
                      </Button>
                    </Box>
                  </Box>

                  {loadingParticipants ? (
                    <CircularProgress />
                  ) : (
                    <Box
                      sx={{
                        maxHeight: 400,
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
                            <TableCell>Email</TableCell>
                            <TableCell>Status</TableCell>
                          </TableRow>
                        </TableHead>
                        <TableBody>
                          {programParticipants.map((participant) => (
                            <TableRow
                              key={participant.id}
                              hover={participant.has_account}
                              onClick={() => participant.has_account && handleParticipantToggle(participant.id)}
                              sx={{ 
                                cursor: participant.has_account ? 'pointer' : 'default',
                                opacity: participant.has_account ? 1 : 0.5
                              }}
                            >
                              <TableCell padding="checkbox">
                                <Checkbox
                                  checked={selectedParticipantIds.includes(participant.id)}
                                  disabled={!participant.has_account}
                                />
                              </TableCell>
                              <TableCell>{participant.name}</TableCell>
                              <TableCell>{participant.customer_number || '—'}</TableCell>
                              <TableCell>{participant.email}</TableCell>
                              <TableCell>
                                {participant.has_account ? (
                                  <Chip label="Ready" size="small" color="success" />
                                ) : (
                                  <Chip label="No Account" size="small" color="warning" />
                                )}
                              </TableCell>
                            </TableRow>
                          ))}
                        </TableBody>
                      </Table>
                    </Box>
                  )}
                </Box>
              )}

              {/* Selected Participants Display for Select Mode */}
              {mode === 'select' && (
                <Box sx={{ mb: 3 }}>
                  <Typography variant="h6" sx={{ mb: 2 }}>
                    Selected Participants ({selectedParticipants.length})
                  </Typography>
                  <Box
                    sx={{
                      maxHeight: 300,
                      overflow: 'auto',
                      border: '1px solid #ddd',
                      borderRadius: 1,
                      p: 2,
                    }}
                  >
                    <Stack spacing={1}>
                      {selectedParticipants.map((participant) => (
                        <Box
                          key={participant.id}
                          sx={{
                            display: 'flex',
                            justifyContent: 'space-between',
                            alignItems: 'center',
                            p: 1,
                            bgcolor: '#f5f5f5',
                            borderRadius: 1,
                          }}
                        >
                          <Box>
                            <Typography variant="body1" fontWeight="medium">
                              {participant.name}
                            </Typography>
                            <Typography variant="caption" color="text.secondary">
                              {participant.customer_number} • {participant.email}
                            </Typography>
                          </Box>
                        </Box>
                      ))}
                    </Stack>
                  </Box>
                  <Box sx={{ mt: 2, display: 'flex', justifyContent: 'flex-end' }}>
                    <Button 
                      variant="outlined" 
                      size="small" 
                      onClick={handleBackStep}
                    >
                      Add/Remove Participants
                    </Button>
                  </Box>
                </Box>
              )}

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
                  disabled={
                    isSubmitting || 
                    (mode === 'program' && selectedParticipantIds.length === 0)
                  }
                >
                  {isSubmitting ? <CircularProgress size={24} /> : 'Create Vouchers'}
                </Button>
                <Button variant="outlined" onClick={handleBackStep} disabled={isSubmitting}>
                  Back
                </Button>
                <Button variant="outlined" onClick={() => redirect('/vouchers')} disabled={isSubmitting}>
                  Cancel
                </Button>
              </Box>
            </>
          )}
        </CardContent>
      </Card>
    </div>
  );
};

export default BulkVoucherCreate;
