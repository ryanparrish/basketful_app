import { useEffect, useState } from 'react';
import {
  Alert,
  AlertTitle,
  Autocomplete,
  Box,
  Button,
  CircularProgress,
  FormControlLabel,
  Switch,
  TextField,
} from '@mui/material';
import { useDataProvider } from 'react-admin';
import type { LowInventoryAlertSettings } from '../../types';

interface GroupOption {
  id: number;
  name: string;
}

interface UserOption {
  id: number;
  username: string;
  email: string;
}

export const InventoryAlertsTab = ({
  settings,
  setSettings,
  onSave,
  saving,
}: {
  settings: LowInventoryAlertSettings;
  setSettings: (v: LowInventoryAlertSettings) => void;
  onSave: () => void;
  saving: boolean;
}) => {
  const dataProvider = useDataProvider();
  const [groupOptions, setGroupOptions] = useState<GroupOption[]>([]);
  const [userOptions, setUserOptions] = useState<UserOption[]>([]);
  const [optionsLoading, setOptionsLoading] = useState(true);

  useEffect(() => {
    const fetchOptions = async () => {
      const [groupsResponse, usersResponse] = await Promise.all([
        dataProvider.getList('groups', {
          pagination: { page: 1, perPage: 100 },
          sort: { field: 'name', order: 'ASC' },
          filter: {},
        }),
        dataProvider.getList('users', {
          pagination: { page: 1, perPage: 200 },
          sort: { field: 'username', order: 'ASC' },
          filter: {},
        }),
      ]);
      setGroupOptions(groupsResponse.data as GroupOption[]);
      setUserOptions(usersResponse.data as UserOption[]);
      setOptionsLoading(false);
    };

    fetchOptions();
  }, [dataProvider]);

  const selectedGroups = groupOptions.filter(g => settings.notify_groups.includes(g.id));
  const selectedUsers = userOptions.filter(u => settings.notify_users.includes(u.id));

  return (
    <Box sx={{ maxWidth: 560 }}>
      <Alert severity="info" sx={{ mb: 3 }}>
        <AlertTitle>How Low Inventory Alerts Work</AlertTitle>
        When any active product's stock drops to or below the threshold, an email alert is sent to
        everyone in the groups and individual users selected below. Each product alerts once per
        low episode — it must recover above the threshold before it can alert again.
      </Alert>

      <TextField
        fullWidth
        type="number"
        label="Low Stock Threshold"
        value={settings.threshold}
        onChange={e => setSettings({ ...settings, threshold: parseInt(e.target.value, 10) || 0 })}
        inputProps={{ min: 0, step: 1 }}
        helperText="Alert when a product's quantity in stock is at or below this value"
        sx={{ mb: 2 }}
      />

      <FormControlLabel
        control={
          <Switch
            checked={settings.enabled}
            onChange={e => setSettings({ ...settings, enabled: e.target.checked })}
          />
        }
        label="Enable Low Inventory Alerts"
        sx={{ mb: 3, display: 'block' }}
      />

      <Autocomplete
        multiple
        loading={optionsLoading}
        options={groupOptions}
        getOptionLabel={option => option.name}
        isOptionEqualToValue={(option, value) => option.id === value.id}
        value={selectedGroups}
        onChange={(_, value) => setSettings({ ...settings, notify_groups: value.map(g => g.id) })}
        renderInput={params => (
          <TextField {...params} label="Notify Groups" placeholder="Add a group…" />
        )}
        sx={{ mb: 2 }}
      />

      <Autocomplete
        multiple
        loading={optionsLoading}
        options={userOptions}
        getOptionLabel={option => `${option.username}${option.email ? ` (${option.email})` : ''}`}
        isOptionEqualToValue={(option, value) => option.id === value.id}
        value={selectedUsers}
        onChange={(_, value) => setSettings({ ...settings, notify_users: value.map(u => u.id) })}
        renderInput={params => (
          <TextField {...params} label="Notify Individual Users" placeholder="Add a user…" />
        )}
        sx={{ mb: 3 }}
      />

      <Button variant="contained" onClick={onSave} disabled={saving}>
        {saving ? <CircularProgress size={20} /> : 'Save Inventory Alert Settings'}
      </Button>
    </Box>
  );
};
