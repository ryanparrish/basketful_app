/**
 * EmailStudioPage — the Email Design Studio.
 *
 * Layout (mirrors familiar commercial builders like Mailchimp/Unlayer):
 * - Top toolbar: subject (+ insert variable), EN/ES tabs, Visual/Code
 *   toggle, preview toggle, Send test, Save.
 * - Left panel: "Start from…" template presets + variables picker.
 * - Center: block canvas + inspector (visual) or Monaco + plain text
 *   (code), with an optional live server-rendered preview column.
 *
 * Save semantics (see studioState.ts): visual saves compile the design
 * to HTML client-side; code saves keep the design but mark it stale for
 * that language. The backend send path always renders html_content.
 */
import { useMemo, useRef, useState } from 'react';
import { useNotify, useRecordContext, useRefresh, useUpdate } from 'react-admin';
import Editor from '@monaco-editor/react';
import SendIcon from '@mui/icons-material/Send';
import SaveIcon from '@mui/icons-material/Save';
import VisibilityIcon from '@mui/icons-material/Visibility';
import DataObjectIcon from '@mui/icons-material/DataObject';
import {
  Alert,
  Box,
  Button,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Divider,
  IconButton,
  Menu,
  MenuItem,
  Stack,
  Tab,
  Tabs,
  TextField,
  ToggleButton,
  ToggleButtonGroup,
  Tooltip,
  Typography,
} from '@mui/material';

import apiClient from '../lib/api/apiClient';
import { EmailServerPreview } from '../resources/logs/EmailServerPreview';
import { EmailStudioEditor } from './EmailStudioEditor';
import { VariablesPanel, type EmailVariableInfo } from './VariablesPanel';
import { TEMPLATE_PRESETS } from './templatePresets';
import {
  buildSavePayload,
  compileDesignToHtml,
  draftFromRecord,
  initialModeForDraft,
  isDesignStale,
  type LanguageDraft,
  type StudioLanguage,
  type StudioMode,
} from './studioState';

export const EmailStudioPage = () => {
  const record = useRecordContext();
  const notify = useNotify();
  const refresh = useRefresh();
  const [update, { isPending: saving }] = useUpdate();

  const [language, setLanguage] = useState<StudioLanguage>('en');
  const [drafts, setDrafts] = useState<Record<StudioLanguage, LanguageDraft> | null>(null);
  const [modes, setModes] = useState<Record<StudioLanguage, StudioMode> | null>(null);
  const [showPreview, setShowPreview] = useState(true);
  const [confirmCodeSaveOpen, setConfirmCodeSaveOpen] = useState(false);
  const [sendingTest, setSendingTest] = useState(false);
  const [variableMenuAnchor, setVariableMenuAnchor] = useState<null | HTMLElement>(null);
  const subjectInputRef = useRef<HTMLInputElement | null>(null);

  // Initialize per-language state once from the record.
  if (record && drafts === null) {
    const recordFields = record as unknown as Parameters<typeof draftFromRecord>[0];
    const en = draftFromRecord(recordFields, 'en');
    const es = draftFromRecord(recordFields, 'es');
    setDrafts({ en, es });
    setModes({ en: initialModeForDraft(en), es: initialModeForDraft(es) });
  }

  const variables: EmailVariableInfo[] = useMemo(
    () => (record?.variables as EmailVariableInfo[]) ?? [],
    [record]
  );

  const draft = drafts?.[language];
  const mode = modes?.[language] ?? 'code';

  const previewDraft = useMemo(
    () =>
      draft
        ? {
            subject: draft.subject,
            html_content:
              mode === 'visual' && draft.designJson
                ? compileDesignToHtml(draft.designJson)
                : draft.htmlContent,
            text_content: draft.textContent,
          }
        : undefined,
    [draft, mode]
  );

  if (!record || !drafts || !modes || !draft || !previewDraft) {
    return <CircularProgress />;
  }

  const updateDraft = (changes: Partial<LanguageDraft>) =>
    setDrafts({ ...drafts, [language]: { ...draft, ...changes } });

  const switchMode = (nextMode: StudioMode) => {
    if (nextMode === mode) return;
    if (nextMode === 'code' && draft.designJson && draft.contentSource !== 'code') {
      // Show the current design's compiled HTML so code mode starts in sync.
      updateDraft({ htmlContent: compileDesignToHtml(draft.designJson) });
    }
    setModes({ ...modes, [language]: nextMode });
  };

  const doSave = async () => {
    try {
      const payload = buildSavePayload(language, mode, draft);
      await update(
        'email-types',
        { id: record.id, data: payload, previousData: record },
        { returnPromise: true }
      );
      updateDraft({ contentSource: mode === 'visual' ? 'design' : 'code' });
      notify(`Saved ${language === 'en' ? 'English' : 'Spanish'} content`, { type: 'success' });
      refresh();
    } catch {
      notify('Error saving email', { type: 'error' });
    }
  };

  const handleSaveClick = () => {
    if (mode === 'code' && draft.designJson && draft.contentSource !== 'code') {
      setConfirmCodeSaveOpen(true);
      return;
    }
    doSave();
  };

  const handleSendTest = async () => {
    setSendingTest(true);
    try {
      const html =
        mode === 'visual' && draft.designJson
          ? compileDesignToHtml(draft.designJson)
          : draft.htmlContent;
      const response = await apiClient.post(`/email-types/${record.id}/send-test/`, {
        subject: draft.subject,
        html_content: html,
        text_content: draft.textContent,
        language,
      });
      notify(response.data.detail, { type: 'success' });
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } }).response?.data?.detail;
      notify(detail || 'Test send failed', { type: 'error' });
    }
    setSendingTest(false);
  };

  const insertVariable = (token: string) => {
    const input = subjectInputRef.current;
    const insertion = `{{ ${token} }}`;
    if (input && document.activeElement === input) {
      const start = input.selectionStart ?? draft.subject.length;
      const end = input.selectionEnd ?? start;
      updateDraft({ subject: draft.subject.slice(0, start) + insertion + draft.subject.slice(end) });
    } else {
      navigator.clipboard.writeText(insertion);
      notify(`Copied ${insertion} — paste it where you need it`, { type: 'info' });
    }
    setVariableMenuAnchor(null);
  };

  return (
    <Stack sx={{ height: 'calc(100vh - 120px)', minHeight: 600 }}>
      {/* ── Top toolbar ─────────────────────────────────────────────── */}
      <Stack direction="row" alignItems="center" spacing={2} sx={{ p: 1, flexWrap: 'wrap' }}>
        <Typography variant="h6" sx={{ mr: 1 }}>{record.display_name}</Typography>
        <Tabs value={language} onChange={(_, next) => setLanguage(next)} sx={{ minHeight: 40 }}>
          <Tab label="English" value="en" sx={{ minHeight: 40 }} />
          <Tab label="Español" value="es" sx={{ minHeight: 40 }} />
        </Tabs>
        <ToggleButtonGroup
          size="small"
          exclusive
          value={mode}
          onChange={(_, next) => next && switchMode(next)}
        >
          <ToggleButton value="visual" data-testid="mode-visual">Visual</ToggleButton>
          <ToggleButton value="code" data-testid="mode-code">
            <DataObjectIcon fontSize="small" sx={{ mr: 0.5 }} /> Code
          </ToggleButton>
        </ToggleButtonGroup>
        <Box sx={{ flex: 1 }} />
        <Tooltip title={showPreview ? 'Hide preview' : 'Show preview'}>
          <IconButton onClick={() => setShowPreview(!showPreview)} color={showPreview ? 'primary' : 'default'}>
            <VisibilityIcon />
          </IconButton>
        </Tooltip>
        <Button
          startIcon={sendingTest ? <CircularProgress size={16} /> : <SendIcon />}
          onClick={handleSendTest}
          disabled={sendingTest}
        >
          Send test
        </Button>
        <Button
          variant="contained"
          startIcon={saving ? <CircularProgress size={16} color="inherit" /> : <SaveIcon />}
          onClick={handleSaveClick}
          disabled={saving}
          data-testid="studio-save"
        >
          Save
        </Button>
      </Stack>

      {/* ── Subject row ─────────────────────────────────────────────── */}
      <Stack direction="row" spacing={1} alignItems="center" sx={{ px: 1, pb: 1 }}>
        <TextField
          fullWidth
          size="small"
          label={`Subject (${language === 'en' ? 'English' : 'Spanish'})`}
          value={draft.subject}
          inputRef={subjectInputRef}
          onChange={e => updateDraft({ subject: e.target.value })}
        />
        <Button size="small" onClick={e => setVariableMenuAnchor(e.currentTarget)}>
          Insert variable
        </Button>
        <Menu
          anchorEl={variableMenuAnchor}
          open={Boolean(variableMenuAnchor)}
          onClose={() => setVariableMenuAnchor(null)}
        >
          {variables
            .filter(variable => variable.kind !== 'list')
            .map(variable => (
              <MenuItem key={variable.token} onClick={() => insertVariable(variable.token)}>
                {variable.label}
              </MenuItem>
            ))}
        </Menu>
      </Stack>

      {language === 'es' && (
        <Alert severity="info" sx={{ mx: 1, mb: 1 }}>
          Spanish content falls back to English wherever it's left blank.
        </Alert>
      )}
      {mode === 'visual' && isDesignStale(draft) && (
        <Alert severity="warning" sx={{ mx: 1, mb: 1 }} data-testid="stale-design-warning">
          This design is older than the current code — the HTML was last edited in Code
          mode. Saving from Visual will overwrite those code edits.
        </Alert>
      )}

      {/* ── Main area ───────────────────────────────────────────────── */}
      <Stack direction="row" sx={{ flex: 1, minHeight: 0, border: 1, borderColor: 'divider' }}>
        {/* Left panel: presets + variables */}
        <Box sx={{ width: 280, flexShrink: 0, borderRight: 1, borderColor: 'divider', overflow: 'auto' }}>
          <Typography variant="subtitle2" sx={{ px: 2, pt: 2 }}>Start from…</Typography>
          <Stack spacing={1} sx={{ p: 2 }}>
            {TEMPLATE_PRESETS.map(preset => (
              <Button
                key={preset.key}
                variant="outlined"
                size="small"
                onClick={() => {
                  updateDraft({ designJson: preset.document });
                  setModes({ ...modes, [language]: 'visual' });
                }}
              >
                {preset.label}
              </Button>
            ))}
          </Stack>
          <Divider />
          <VariablesPanel variables={variables} />
        </Box>

        {/* Editor */}
        <Box sx={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column' }}>
          {mode === 'visual' ? (
            <EmailStudioEditor
              document={draft.designJson}
              onChange={designJson => updateDraft({ designJson })}
            />
          ) : (
            <Stack sx={{ flex: 1, minHeight: 0 }}>
              <Editor
                height="60%"
                language="html"
                theme="vs-dark"
                value={draft.htmlContent}
                onChange={value => updateDraft({ htmlContent: value ?? '' })}
                options={{ minimap: { enabled: false }, wordWrap: 'on', fontSize: 13 }}
              />
              <TextField
                label={`Plain text (${language === 'en' ? 'English' : 'Spanish'})`}
                multiline
                value={draft.textContent}
                onChange={e => updateDraft({ textContent: e.target.value })}
                sx={{ flex: 1, m: 1, '& .MuiInputBase-root': { height: '100%', alignItems: 'start' } }}
              />
            </Stack>
          )}
        </Box>

        {/* Live preview */}
        {showPreview && (
          <Box sx={{ width: '38%', flexShrink: 0, borderLeft: 1, borderColor: 'divider', overflow: 'auto', p: 1 }}>
            <EmailServerPreview emailTypeId={record.id} draft={previewDraft} />
          </Box>
        )}
      </Stack>

      {/* ── Code-save confirmation ──────────────────────────────────── */}
      <Dialog open={confirmCodeSaveOpen} onClose={() => setConfirmCodeSaveOpen(false)}>
        <DialogTitle>Save code edits?</DialogTitle>
        <DialogContent>
          <Alert severity="warning">
            Saving from Code mode disconnects the visual design for this language. The
            design is kept, but it becomes out of date until you save from Visual again.
          </Alert>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setConfirmCodeSaveOpen(false)}>Cancel</Button>
          <Button
            variant="contained"
            color="warning"
            onClick={() => {
              setConfirmCodeSaveOpen(false);
              doSave();
            }}
          >
            Save code edits
          </Button>
        </DialogActions>
      </Dialog>
    </Stack>
  );
};

export default EmailStudioPage;
