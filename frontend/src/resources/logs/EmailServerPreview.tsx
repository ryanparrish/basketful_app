/**
 * EmailServerPreview — server-rendered email preview with sample data.
 *
 * Calls GET/POST /email-types/{id}/preview/ so staff see the email as a
 * participant would (variables substituted, per-language), instead of
 * raw {{ placeholders }}. Pass `draft` to preview unsaved content
 * (POST); omit it to preview the saved template (GET).
 */
import { useCallback, useEffect, useState } from 'react';
import {
  Alert,
  Box,
  CircularProgress,
  Tab,
  Tabs,
  ToggleButton,
  ToggleButtonGroup,
  Typography,
} from '@mui/material';
import apiClient from '../../lib/api/apiClient';

export interface EmailPreviewDraft {
  subject?: string;
  html_content?: string;
  text_content?: string;
}

interface RenderedPreview {
  subject: string;
  html: string;
  text: string;
  language: string;
}

export type PreviewLanguage = 'en' | 'es';

export const EmailServerPreview = ({
  emailTypeId,
  draft,
  debounceMs = 800,
}: {
  emailTypeId: number | string;
  draft?: EmailPreviewDraft;
  debounceMs?: number;
}) => {
  const [language, setLanguage] = useState<PreviewLanguage>('en');
  const [preview, setPreview] = useState<RenderedPreview | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [contentTab, setContentTab] = useState<'html' | 'text'>('html');

  const fetchPreview = useCallback(async () => {
    setLoading(true);
    try {
      const response = draft
        ? await apiClient.post(`/email-types/${emailTypeId}/preview/`, {
            ...draft,
            language,
          })
        : await apiClient.get(`/email-types/${emailTypeId}/preview/`, {
            params: { language },
          });
      setPreview(response.data);
      setError(null);
    } catch (err: unknown) {
      const detail =
        (err as { response?: { data?: { detail?: string; field?: string } } })
          .response?.data;
      setError(
        detail?.detail
          ? `${detail.field ? `${detail.field}: ` : ''}${detail.detail}`
          : 'Failed to render preview'
      );
    }
    setLoading(false);
  }, [emailTypeId, language, draft]);

  useEffect(() => {
    const timer = setTimeout(fetchPreview, draft ? debounceMs : 0);
    return () => clearTimeout(timer);
  }, [fetchPreview, draft, debounceMs]);

  return (
    <Box>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 1 }}>
        <ToggleButtonGroup
          size="small"
          exclusive
          value={language}
          onChange={(_, next) => next && setLanguage(next)}
        >
          <ToggleButton value="en">English</ToggleButton>
          <ToggleButton value="es">Español</ToggleButton>
        </ToggleButtonGroup>
        <Tabs
          value={contentTab}
          onChange={(_, next) => setContentTab(next)}
          sx={{ minHeight: 36 }}
        >
          <Tab label="HTML" value="html" sx={{ minHeight: 36 }} />
          <Tab label="Plain Text" value="text" sx={{ minHeight: 36 }} />
        </Tabs>
        {loading && <CircularProgress size={18} />}
      </Box>

      {error ? (
        <Alert severity="error" sx={{ mb: 1 }}>
          {error}
        </Alert>
      ) : (
        preview && (
          <>
            <Typography variant="subtitle2" sx={{ mb: 1 }}>
              Subject: {preview.subject}
            </Typography>
            {contentTab === 'html' ? (
              <Box
                sx={{
                  border: '1px solid #e0e0e0',
                  borderRadius: 1,
                  overflow: 'hidden',
                }}
              >
                <iframe
                  srcDoc={preview.html}
                  style={{
                    width: '100%',
                    height: 500,
                    border: 'none',
                    display: 'block',
                  }}
                  sandbox="allow-same-origin"
                  title="Email Preview"
                />
              </Box>
            ) : (
              <Box
                component="pre"
                sx={{
                  border: '1px solid #e0e0e0',
                  borderRadius: 1,
                  p: 2,
                  whiteSpace: 'pre-wrap',
                  fontFamily: 'monospace',
                  fontSize: '0.85rem',
                  maxHeight: 500,
                  overflow: 'auto',
                }}
              >
                {preview.text || '(no plain-text content)'}
              </Box>
            )}
          </>
        )
      )}
    </Box>
  );
};
