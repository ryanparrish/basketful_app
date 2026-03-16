/**
 * FailedOrderAttempt Resource — read-only audit log for failed order submissions.
 * Mirrors FailedOrderAttemptAdmin from apps/orders/admin.py
 */
import {
  List,
  Datagrid,
  TextField,
  DateField,
  Show,
  SimpleShowLayout,
  FunctionField,
  useRecordContext,
  TopToolbar,
  ListButton,
  FilterButton,
  SearchInput,
  SelectInput,
  usePermissions,
  DeleteButton,
  type RaRecord,
} from 'react-admin';
import { Box, Chip, Typography } from '@mui/material';
import { API_URL } from '../utils/apiUrl';

// ─── Field Components ────────────────────────────────────────────────────────

const ProgramPauseField = () => {
  const record = useRecordContext();
  if (!record) return null;
  if (record.program_pause_active) {
    return (
      <Chip
        label={`⚠ ${record.program_pause_name || 'Active'}`}
        color="warning"
        size="small"
      />
    );
  }
  return <Chip label="✓ Normal" color="success" size="small" />;
};

const BalanceStatusField = () => {
  const record = useRecordContext();
  if (!record) return <span>—</span>;
  const food = parseFloat(record.food_total || '0');
  const available = parseFloat(record.available_balance || '0');
  if (!food || !available) return <span>—</span>;
  const over = food > available;
  return (
    <span style={{ color: over ? '#ef5350' : '#4caf50', fontWeight: 'bold' }}>
      ${food.toFixed(2)} {over ? '>' : '≤'} ${available.toFixed(2)}
    </span>
  );
};

const ErrorSummaryField = () => {
  const record = useRecordContext();
  if (!record || !record.error_summary) return <span>—</span>;
  const text = record.error_summary.length > 100
    ? `${record.error_summary.substring(0, 100)}…`
    : record.error_summary;
  return <span title={record.error_summary}>{text}</span>;
};

const CartSnapshotField = () => {
  const record = useRecordContext();
  if (!record || !record.cart_snapshot) return <Typography variant="body2">—</Typography>;
  return (
    <Box
      component="pre"
      sx={{
        maxHeight: 300,
        overflow: 'auto',
        backgroundColor: '#f5f5f5',
        p: 2,
        borderRadius: 1,
        fontSize: '0.75rem',
        fontFamily: 'monospace',
        whiteSpace: 'pre-wrap',
        wordBreak: 'break-word',
      }}
    >
      {JSON.stringify(record.cart_snapshot, null, 2)}
    </Box>
  );
};

const ValidationErrorsField = () => {
  const record = useRecordContext();
  if (!record || !record.validation_errors_display) {
    return <Typography variant="body2">—</Typography>;
  }
  return (
    <Box
      component="pre"
      sx={{
        maxHeight: 300,
        overflow: 'auto',
        backgroundColor: '#fff3e0',
        p: 2,
        borderRadius: 1,
        fontSize: '0.75rem',
        fontFamily: 'monospace',
        whiteSpace: 'pre-wrap',
        wordBreak: 'break-word',
      }}
    >
      {record.validation_errors_display}
    </Box>
  );
};

// ─── Filters ─────────────────────────────────────────────────────────────────

const failedOrderFilters = [
  <SearchInput source="q" alwaysOn key="search" />,
  <SelectInput
    source="program_pause_active"
    label="Program Pause"
    choices={[
      { id: 'true', name: '⚠ Active Pause' },
      { id: 'false', name: '✓ Normal' },
    ]}
    key="pause"
  />,
];

// ─── List ─────────────────────────────────────────────────────────────────────

export const FailedOrderAttemptList = () => (
  <List
    filters={failedOrderFilters}
    sort={{ field: 'created_at', order: 'DESC' }}
    actions={<TopToolbar><FilterButton /></TopToolbar>}
  >
    <Datagrid rowClick="show" bulkActionButtons={false}>
      <DateField source="created_at" showTime label="Date" />
      <TextField source="participant_name" label="Participant" />
      <FunctionField
        label="Total Attempted"
        render={(record: RaRecord) =>
          record.total_attempted ? `$${parseFloat(record.total_attempted).toFixed(2)}` : '—'
        }
      />
      <FunctionField label="Error" render={() => <ErrorSummaryField />} />
      <FunctionField label="Program Pause" render={() => <ProgramPauseField />} />
      <FunctionField label="Balance Check" render={() => <BalanceStatusField />} />
    </Datagrid>
  </List>
);

// ─── Show Actions ─────────────────────────────────────────────────────────────

const FailedOrderAttemptShowActions = () => {
  const { permissions } = usePermissions();
  return (
    <TopToolbar>
      <ListButton />
      {permissions?.is_superuser && (
        <DeleteButton mutationMode="pessimistic" />
      )}
    </TopToolbar>
  );
};

// ─── Show ─────────────────────────────────────────────────────────────────────

export const FailedOrderAttemptShow = () => (
  <Show actions={<FailedOrderAttemptShowActions />}>
    <SimpleShowLayout>
      {/* Order Context */}
      <Typography variant="h6" sx={{ mt: 1, fontWeight: 'bold' }}>Order Context</Typography>
      <TextField source="participant_name" label="Participant" />
      <TextField source="idempotency_key" label="Idempotency Key" />
      <DateField source="created_at" showTime label="Date" />
      <TextField source="ip_address" label="IP Address" />
      <TextField source="user_agent" label="User Agent" />

      {/* Cart Details */}
      <Typography variant="h6" sx={{ mt: 2, fontWeight: 'bold' }}>Cart Details</Typography>
      <FunctionField
        label="Total Attempted"
        render={(record: RaRecord) =>
          record.total_attempted ? `$${parseFloat(record.total_attempted).toFixed(2)}` : '—'
        }
      />
      <FunctionField
        label="Food Total"
        render={(record: RaRecord) =>
          record.food_total ? `$${parseFloat(record.food_total).toFixed(2)}` : '—'
        }
      />
      <FunctionField
        label="Hygiene Total"
        render={(record: RaRecord) =>
          record.hygiene_total ? `$${parseFloat(record.hygiene_total).toFixed(2)}` : '—'
        }
      />
      <FunctionField label="Cart Contents" render={() => <CartSnapshotField />} />

      {/* Balances at Time of Failure */}
      <Typography variant="h6" sx={{ mt: 2, fontWeight: 'bold' }}>Balances at Time of Failure</Typography>
      <FunctionField
        label="Available Balance"
        render={(record: RaRecord) =>
          record.available_balance ? `$${parseFloat(record.available_balance).toFixed(2)}` : '—'
        }
      />
      <FunctionField
        label="Hygiene Balance"
        render={(record: RaRecord) =>
          record.hygiene_balance ? `$${parseFloat(record.hygiene_balance).toFixed(2)}` : '—'
        }
      />
      <FunctionField label="Balance Check" render={() => <BalanceStatusField />} />

      {/* Program Pause Context */}
      <Typography variant="h6" sx={{ mt: 2, fontWeight: 'bold' }}>Program Pause Context</Typography>
      <FunctionField label="Program Pause Status" render={() => <ProgramPauseField />} />
      <TextField source="program_pause_name" label="Pause Name" emptyText="—" />
      <TextField source="voucher_multiplier" label="Voucher Multiplier" emptyText="—" />
      <TextField source="active_voucher_count" label="Active Voucher Count" emptyText="—" />

      {/* Validation Errors */}
      <Typography variant="h6" sx={{ mt: 2, fontWeight: 'bold' }}>Validation Errors</Typography>
      <TextField source="error_summary" label="Summary" emptyText="—" />
      <FunctionField label="Detailed Errors" render={() => <ValidationErrorsField />} />
    </SimpleShowLayout>
  </Show>
);

export { API_URL };
