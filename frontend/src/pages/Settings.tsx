/**
 * Settings Page
 * 
 * Manage system-wide settings including order window, email, and branding.
 */
import { useState, useEffect } from 'react';
import {
  Title,
  useDataProvider,
  useNotify,
  Loading,
} from 'react-admin';
import {
  Card,
  CardContent,
  CardHeader,
  Button,
  TextField,
  Switch,
  FormControlLabel,
  Tabs,
  Tab,
  Box,
  Alert,
} from '@mui/material';

interface TabPanelProps {
  children?: React.ReactNode;
  index: number;
  value: number;
}

const TabPanel = ({ children, value, index }: TabPanelProps) => (
  <div hidden={value !== index} style={{ padding: '20px 0' }}>
    {value === index && children}
  </div>
);

interface OrderWindowSettings {
  id: number;
  hours_before_class: number;
  hours_before_close: number;
  enabled: boolean;
}

interface EmailSettings {
  id: number;
  from_email_default: string;
  reply_to_default: string;
  effective_from_email: string;
}

interface BrandingSettings {
  id: number;
  organization_name: string;
  logo: string | null;
}

interface VoucherSettings {
  id: number;
  adult_amount: number;
  child_amount: number;
  infant_modifier: number;
  active: boolean;
}

export const Settings = () => {
  const dataProvider = useDataProvider();
  const notify = useNotify();
  const [tab, setTab] = useState(0);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  // Settings state
  const [orderWindow, setOrderWindow] = useState<OrderWindowSettings | null>(null);
  const [email, setEmail] = useState<EmailSettings | null>(null);
  const [branding, setBranding] = useState<BrandingSettings | null>(null);
  const [voucher, setVoucher] = useState<VoucherSettings | null>(null);

  // Fetch all settings
  useEffect(() => {
    const fetchSettings = async () => {
      try {
        const [owResponse, emailResponse, brandingResponse, voucherResponse] =
          await Promise.all([
            dataProvider.getOne('settings/order-window-settings', { id: 'current' }),
            dataProvider.getOne('settings/email-settings', { id: 'current' }),
            dataProvider.getOne('settings/branding-settings', { id: 'current' }),
            dataProvider.getList('voucher-settings', {
              pagination: { page: 1, perPage: 1 },
              filter: { active: true },
              sort: { field: 'id', order: 'DESC' },
            }),
          ]);

        setOrderWindow(owResponse.data as OrderWindowSettings);
        setEmail(emailResponse.data as EmailSettings);
        setBranding(brandingResponse.data as BrandingSettings);
        if (voucherResponse.data.length > 0) {
          setVoucher(voucherResponse.data[0] as VoucherSettings);
        }
      } catch (error) {
        notify('Error loading settings', { type: 'error' });
      }
      setLoading(false);
    };

    fetchSettings();
  }, [dataProvider, notify]);

  // Save Order Window Settings
  const saveOrderWindow = async () => {
    if (!orderWindow) return;
    setSaving(true);
    try {
      await dataProvider.update('settings/order-window-settings', {
        id: 'current',
        data: orderWindow,
        previousData: orderWindow,
      });
      notify('Order window settings saved', { type: 'success' });
    } catch (error) {
      notify('Error saving settings', { type: 'error' });
    }
    setSaving(false);
  };

  // Save Email Settings
  const saveEmail = async () => {
    if (!email) return;
    setSaving(true);
    try {
      await dataProvider.update('settings/email-settings', {
        id: 'current',
        data: email,
        previousData: email,
      });
      notify('Email settings saved', { type: 'success' });
    } catch (error) {
      notify('Error saving settings', { type: 'error' });
    }
    setSaving(false);
  };

  // Save Branding Settings
  const saveBranding = async () => {
    if (!branding) return;
    setSaving(true);
    try {
      await dataProvider.update('settings/branding-settings', {
        id: 'current',
        data: branding,
        previousData: branding,
      });
      notify('Branding settings saved', { type: 'success' });
    } catch (error) {
      notify('Error saving settings', { type: 'error' });
    }
    setSaving(false);
  };

  // Save Voucher Settings
  const saveVoucher = async () => {
    if (!voucher) return;
    setSaving(true);
    try {
      await dataProvider.update('voucher-settings', {
        id: voucher.id,
        data: voucher,
        previousData: voucher,
      });
      notify('Voucher settings saved', { type: 'success' });
    } catch (error) {
      notify('Error saving settings', { type: 'error' });
    }
    setSaving(false);
  };

  if (loading) return <Loading />;

  return (
    <div>
      <Title title="Settings" />

      <Card sx={{ m: 2 }}>
        <CardHeader title="System Settings" />
        <CardContent>
          <Tabs value={tab} onChange={(_, v) => setTab(v)}>
            <Tab label="Order Window" />
            <Tab label="Email" />
            <Tab label="Branding" />
            <Tab label="Vouchers" />
          </Tabs>

          {/* Order Window Tab */}
          <TabPanel value={tab} index={0}>
            {orderWindow && (
              <Box sx={{ maxWidth: 500 }}>
                <FormControlLabel
                  control={
                    <Switch
                      checked={orderWindow.enabled}
                      onChange={(e) =>
                        setOrderWindow({ ...orderWindow, enabled: e.target.checked })
                      }
                    />
                  }
                  label="Enable Order Window Restrictions"
                />

                <Alert severity="info" sx={{ my: 2 }}>
                  Control when participants can place orders relative to their
                  class time.
                </Alert>

                <TextField
                  fullWidth
                  type="number"
                  label="Hours Before Class (Window Opens)"
                  value={orderWindow.hours_before_class}
                  onChange={(e) =>
                    setOrderWindow({
                      ...orderWindow,
                      hours_before_class: parseInt(e.target.value) || 0,
                    })
                  }
                  helperText="Orders can be placed this many hours before class starts"
                  sx={{ mb: 2 }}
                />

                <TextField
                  fullWidth
                  type="number"
                  label="Hours Before Close (Window Closes)"
                  value={orderWindow.hours_before_close}
                  onChange={(e) =>
                    setOrderWindow({
                      ...orderWindow,
                      hours_before_close: parseInt(e.target.value) || 0,
                    })
                  }
                  helperText="Orders must be placed at least this many hours before class (0 = at class time)"
                  sx={{ mb: 3 }}
                />

                <Button
                  variant="contained"
                  onClick={saveOrderWindow}
                  disabled={saving}
                >
                  Save Order Window Settings
                </Button>
              </Box>
            )}
          </TabPanel>

          {/* Email Tab */}
          <TabPanel value={tab} index={1}>
            {email && (
              <Box sx={{ maxWidth: 500 }}>
                <TextField
                  fullWidth
                  label="Default From Email"
                  value={email.from_email_default}
                  onChange={(e) =>
                    setEmail({ ...email, from_email_default: e.target.value })
                  }
                  helperText="Leave blank to use system default"
                  sx={{ mb: 2 }}
                />

                <TextField
                  fullWidth
                  label="Reply-To Email"
                  value={email.reply_to_default}
                  onChange={(e) =>
                    setEmail({ ...email, reply_to_default: e.target.value })
                  }
                  sx={{ mb: 2 }}
                />

                <Alert severity="info" sx={{ mb: 3 }}>
                  Effective From Email: {email.effective_from_email || 'System Default'}
                </Alert>

                <Button variant="contained" onClick={saveEmail} disabled={saving}>
                  Save Email Settings
                </Button>
              </Box>
            )}
          </TabPanel>

          {/* Branding Tab */}
          <TabPanel value={tab} index={2}>
            {branding && (
              <Box sx={{ maxWidth: 500 }}>
                <TextField
                  fullWidth
                  label="Organization Name"
                  value={branding.organization_name}
                  onChange={(e) =>
                    setBranding({ ...branding, organization_name: e.target.value })
                  }
                  helperText="Displayed on printed orders and documents"
                  sx={{ mb: 3 }}
                />

                {branding.logo && (
                  <Box sx={{ mb: 2 }}>
                    <img
                      src={branding.logo}
                      alt="Organization Logo"
                      style={{ maxWidth: 200, maxHeight: 100 }}
                    />
                  </Box>
                )}

                <Button variant="contained" onClick={saveBranding} disabled={saving}>
                  Save Branding Settings
                </Button>
              </Box>
            )}
          </TabPanel>

          {/* Voucher Tab */}
          <TabPanel value={tab} index={3}>
            {voucher ? (
              <Box sx={{ maxWidth: 500 }}>
                <TextField
                  fullWidth
                  type="number"
                  label="Adult Amount ($)"
                  value={voucher.adult_amount}
                  onChange={(e) =>
                    setVoucher({
                      ...voucher,
                      adult_amount: parseFloat(e.target.value) || 0,
                    })
                  }
                  inputProps={{ step: 0.5 }}
                  sx={{ mb: 2 }}
                />

                <TextField
                  fullWidth
                  type="number"
                  label="Child Amount ($)"
                  value={voucher.child_amount}
                  onChange={(e) =>
                    setVoucher({
                      ...voucher,
                      child_amount: parseFloat(e.target.value) || 0,
                    })
                  }
                  inputProps={{ step: 0.5 }}
                  sx={{ mb: 2 }}
                />

                <TextField
                  fullWidth
                  type="number"
                  label="Infant Modifier ($)"
                  value={voucher.infant_modifier}
                  onChange={(e) =>
                    setVoucher({
                      ...voucher,
                      infant_modifier: parseFloat(e.target.value) || 0,
                    })
                  }
                  inputProps={{ step: 0.5 }}
                  helperText="Additional amount added for infants"
                  sx={{ mb: 3 }}
                />

                <Button variant="contained" onClick={saveVoucher} disabled={saving}>
                  Save Voucher Settings
                </Button>
              </Box>
            ) : (
              <Alert severity="warning">
                No active voucher settings found. Create one in the Voucher
                Settings resource.
              </Alert>
            )}
          </TabPanel>
        </CardContent>
      </Card>
    </div>
  );
};

export default Settings;
