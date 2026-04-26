/**
 * Settings Page
 *
 * Manage system-wide settings including order window, email, and branding.
 */
import { useState, useEffect } from 'react';
import { Title, useDataProvider, useNotify, Loading } from 'react-admin';
import { Card, CardContent, CardHeader, CircularProgress, Tab, Tabs } from '@mui/material';

import { TabPanel } from './settings/components/TabPanel';
import { OrderWindowDashboard } from './settings/components/order-window/OrderWindowDashboard';
import { EmailTab } from './settings/components/tabs/EmailTab';
import { BrandingTab } from './settings/components/tabs/BrandingTab';
import { VoucherTab } from './settings/components/tabs/VoucherTab';
import { ProgramPausesTab } from './settings/components/tabs/ProgramPausesTab';
import { HygieneTab } from './settings/components/tabs/HygieneTab';
import type {
  BrandingSettings,
  EmailSettings,
  HygieneSettings,
  OrderWindowSettings,
  VoucherSettings,
} from './settings/types';

export const Settings = () => {
  const dataProvider = useDataProvider();
  const notify = useNotify();
  const [tab, setTab] = useState(0);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  const [orderWindow, setOrderWindow] = useState<OrderWindowSettings | null>(null);
  const [email, setEmail] = useState<EmailSettings | null>(null);
  const [branding, setBranding] = useState<BrandingSettings | null>(null);
  const [voucher, setVoucher] = useState<VoucherSettings | null>(null);
  const [hygiene, setHygiene] = useState<HygieneSettings | null>(null);

  useEffect(() => {
    const fetchSettings = async () => {
      try {
        const [owResponse, emailResponse, brandingResponse, voucherResponse, hygieneResponse] =
          await Promise.all([
            dataProvider.getOne('settings/order-window-settings', { id: 'current' }),
            dataProvider.getOne('settings/email-settings', { id: 'current' }),
            dataProvider.getOne('settings/branding-settings', { id: 'current' }),
            dataProvider.getList('voucher-settings', {
              pagination: { page: 1, perPage: 1 },
              filter: { active: true },
              sort: { field: 'id', order: 'DESC' },
            }),
            dataProvider.getOne('hygiene-settings', { id: 'current' }),
          ]);

        setOrderWindow(owResponse.data as OrderWindowSettings);
        setEmail(emailResponse.data as EmailSettings);
        setBranding(brandingResponse.data as BrandingSettings);
        if (voucherResponse.data.length > 0) {
          setVoucher(voucherResponse.data[0] as VoucherSettings);
        }
        setHygiene(hygieneResponse.data as HygieneSettings);
      } catch {
        notify('Error loading settings', { type: 'error' });
      }
      setLoading(false);
    };

    fetchSettings();
  }, [dataProvider, notify]);

  const saveOrderWindow = async (updatedSettings?: OrderWindowSettings) => {
    const data = updatedSettings ?? orderWindow;
    if (!data) return;
    setSaving(true);
    try {
      await dataProvider.update('settings/order-window-settings', {
        id: 'current',
        data,
        previousData: data,
      });
      setOrderWindow(data);
      notify('Order window settings saved', { type: 'success' });
    } catch {
      notify('Error saving settings', { type: 'error' });
    }
    setSaving(false);
  };

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
    } catch {
      notify('Error saving settings', { type: 'error' });
    }
    setSaving(false);
  };

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
    } catch {
      notify('Error saving settings', { type: 'error' });
    }
    setSaving(false);
  };

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
    } catch {
      notify('Error saving settings', { type: 'error' });
    }
    setSaving(false);
  };

  const saveHygiene = async () => {
    if (!hygiene) return;
    setSaving(true);
    try {
      await dataProvider.update('hygiene-settings', {
        id: 'current',
        data: hygiene,
        previousData: hygiene,
      });
      notify('Hygiene settings saved', { type: 'success' });
    } catch {
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
            <Tab label="Program Pauses" />
            <Tab label="Hygiene" />
          </Tabs>

          <TabPanel value={tab} index={0}>
            {orderWindow ? (
              <OrderWindowDashboard
                globalSettings={orderWindow}
                onSaveGlobal={saveOrderWindow}
                saving={saving}
              />
            ) : (
              <CircularProgress size={24} />
            )}
          </TabPanel>

          <TabPanel value={tab} index={1}>
            {email && (
              <EmailTab email={email} setEmail={setEmail} onSave={saveEmail} saving={saving} />
            )}
          </TabPanel>

          <TabPanel value={tab} index={2}>
            {branding && (
              <BrandingTab
                branding={branding}
                setBranding={setBranding}
                onSave={saveBranding}
                saving={saving}
              />
            )}
          </TabPanel>

          <TabPanel value={tab} index={3}>
            <VoucherTab
              voucher={voucher}
              setVoucher={setVoucher}
              onSave={saveVoucher}
              saving={saving}
            />
          </TabPanel>

          <TabPanel value={tab} index={4}>
            <ProgramPausesTab />
          </TabPanel>

          <TabPanel value={tab} index={5}>
            {hygiene && (
              <HygieneTab
                hygiene={hygiene}
                setHygiene={setHygiene}
                onSave={saveHygiene}
                saving={saving}
              />
            )}
          </TabPanel>
        </CardContent>
      </Card>
    </div>
  );
};

export default Settings;
