/**
 * Branding Settings — singleton resource.
 * Nav link goes directly to /branding-settings/current/edit, bypassing the list.
 */
import {
  Edit,
  SimpleForm,
  TextInput,
  ImageInput,
  ImageField,
  useNotify,
  SaveButton,
  Toolbar,
} from 'react-admin';
import { Box, Typography } from '@mui/material';
import BrushIcon from '@mui/icons-material/Brush';
import { API_URL } from '../utils/apiUrl';

export { BrushIcon as BrandingSettingsIcon };

/**
 * Singleton edit — always edits PK=1 via the /current/ endpoint.
 * We override the default save to PATCH /settings/branding-settings/current/.
 */
const BrandingToolbar = () => (
  <Toolbar>
    <SaveButton />
  </Toolbar>
);

export const BrandingSettingsEdit = () => {
  const notify = useNotify();

  const handleSave = async (values: Record<string, unknown>) => {
    const token = localStorage.getItem('accessToken');
    const formData = new FormData();

    if (values.organization_name) {
      formData.append('organization_name', values.organization_name as string);
    }

    // ImageInput wraps uploaded files in { rawFile, src, title }
    const logoValue = values.logo as { rawFile?: File } | string | null | undefined;
    if (logoValue && typeof logoValue === 'object' && logoValue.rawFile instanceof File) {
      formData.append('logo', logoValue.rawFile);
    }

    const res = await fetch(`${API_URL}/api/v1/settings/branding-settings/current/`, {
      method: 'PATCH',
      headers: { Authorization: `Bearer ${token}` },
      body: formData,
    });

    if (!res.ok) {
      notify('Failed to save branding settings', { type: 'error' });
      return;
    }
    notify('Branding settings saved', { type: 'success' });
  };

  return (
    <Edit
      resource="branding-settings"
      id="current"
      mutationMode="pessimistic"
      mutationOptions={{ onSuccess: () => notify('Branding settings saved', { type: 'success' }) }}
      title="Branding Settings"
    >
      <SimpleForm toolbar={<BrandingToolbar />} onSubmit={handleSave}>
        <Box sx={{ maxWidth: 600 }}>
          <Typography variant="h6" gutterBottom>
            Organization Branding
          </Typography>

          <TextInput
            source="organization_name"
            label="Organization Name"
            fullWidth
            helperText="Displayed in print views and emails"
          />

          <Box sx={{ mt: 2 }}>
            <Typography variant="subtitle2" color="text.secondary" gutterBottom>
              Logo
            </Typography>
            <ImageInput
              source="logo"
              label="Organization Logo"
              accept={{ 'image/*': ['.png', '.jpg', '.jpeg', '.svg', '.webp'] }}
              maxSize={5_000_000}
              placeholder={
                <Typography variant="body2" color="text.secondary">
                  Drop a logo here, or click to select (PNG, JPG, SVG — max 5MB)
                </Typography>
              }
            >
              <ImageField source="src" title="title" />
            </ImageInput>
          </Box>
        </Box>
      </SimpleForm>
    </Edit>
  );
};
