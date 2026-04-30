/**
 * EmailLog Resource — read-only audit trail of all sent emails.
 * Mirrors EmailLogAdmin from apps/log/admin.py
 */
import {
  List,
  Datagrid,
  TextField,
  DateField,
  Show,
  SimpleShowLayout,
  TopToolbar,
  ListButton,
  ShowButton,
  FilterButton,
  ExportButton,
  SearchInput,
  SelectInput,
  ReferenceInput,
  useRecordContext,
} from 'react-admin';
import { Link } from '@mui/material';
import { EmailStatusChip, DeliveryStatusChip } from './shared';

const STATUS_CHOICES = [
  { id: 'sent', name: 'Sent' },
  { id: 'failed', name: 'Failed' },
];

const DELIVERY_STATUS_CHOICES = [
  { id: 'unknown', name: 'Pending' },
  { id: 'delivered', name: 'Delivered' },
  { id: 'bounced', name: 'Bounced' },
  { id: 'complained', name: 'Complained' },
  { id: 'unsubscribed', name: 'Unsubscribed' },
  { id: 'failed', name: 'Failed' },
];

const emailLogFilters = [
  <SearchInput source="q" alwaysOn key="search" />,
  <SelectInput source="status" choices={STATUS_CHOICES} key="status" />,
  <SelectInput
    source="delivery_status"
    label="Delivery Status"
    choices={DELIVERY_STATUS_CHOICES}
    key="delivery_status"
  />,
  <ReferenceInput source="email_type" reference="email-types" key="email_type">
    <SelectInput optionText="display_name" />
  </ReferenceInput>,
];

// ─── Mailgun deep-link field ──────────────────────────────────────────────────

const MailgunLink = () => {
  const record = useRecordContext();
  if (!record?.message_id) return <span>—</span>;
  const url = `https://app.mailgun.com/app/logs?messageId=${encodeURIComponent(record.message_id)}`;
  return (
    <Link href={url} target="_blank" rel="noopener noreferrer" sx={{ fontSize: '0.875rem' }}>
      {record.message_id}
    </Link>
  );
};
MailgunLink.displayName = 'MailgunLink';

// ─── List ─────────────────────────────────────────────────────────────────────

export const EmailLogList = () => (
  <List
    filters={emailLogFilters}
    sort={{ field: 'sent_at', order: 'DESC' }}
    perPage={25}
    actions={
      <TopToolbar>
        <FilterButton />
        <ExportButton />
      </TopToolbar>
    }
  >
    <Datagrid rowClick="show" bulkActionButtons={false}>
      <DateField source="sent_at" label="Sent At" showTime />
      <TextField source="user_email" label="Recipient" />
      <TextField source="email_type_name" label="Email Type" />
      <TextField source="subject" />
      <EmailStatusChip />
      <DeliveryStatusChip />
      <ShowButton />
    </Datagrid>
  </List>
);

// ─── Show ─────────────────────────────────────────────────────────────────────

export const EmailLogShow = () => (
  <Show
    actions={
      <TopToolbar>
        <ListButton />
      </TopToolbar>
    }
  >
    <SimpleShowLayout>
      <DateField source="sent_at" label="Sent At" showTime />
      <TextField source="user_email" label="Recipient" />
      <TextField source="email_type_name" label="Email Type" />
      <TextField source="subject" />
      <EmailStatusChip />
      <TextField source="error_message" label="Error Details" emptyText="—" />
      <DeliveryStatusChip />
      <DateField source="delivery_checked_at" label="Last Delivery Check" showTime emptyText="Not yet checked" />
      <MailgunLink />
    </SimpleShowLayout>
  </Show>
);
