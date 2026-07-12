/**
 * EmailStudioEditor — controlled wrapper around the vendored
 * EmailBuilder.js editor (canvas + inspector panel + screen-size toggle).
 *
 * The vendored editor keeps its state in a module-level zustand store;
 * this wrapper makes it behave like a controlled component: `document`
 * resets the store when it changes identity (e.g. switching language
 * tabs or loading a template preset), and `onChange` fires on every
 * block edit.
 */
import { useEffect, useRef } from 'react';
import { MonitorOutlined, PhoneIphoneOutlined } from '@mui/icons-material';
import {
  Box,
  Stack,
  ToggleButton,
  ToggleButtonGroup,
  Tooltip,
} from '@mui/material';

import EditorBlock from './vendor/documents/editor/EditorBlock';
import {
  EMPTY_EMAIL_MESSAGE,
  resetDocument,
  setSelectedScreenSize,
  subscribeToDocument,
  useSelectedScreenSize,
} from './vendor/documents/editor/EditorContext';
import type { TEditorConfiguration } from './vendor/documents/editor/core';
import InspectorDrawer from './vendor/App/InspectorDrawer';
import ToggleInspectorPanelButton from './vendor/App/InspectorDrawer/ToggleInspectorPanelButton';

export type { TEditorConfiguration };
export { EMPTY_EMAIL_MESSAGE };

export const EmailStudioEditor = ({
  document,
  onChange,
}: {
  /** The design document to edit. New identity resets the editor. */
  document: TEditorConfiguration | null;
  onChange: (document: TEditorConfiguration) => void;
}) => {
  const selectedScreenSize = useSelectedScreenSize();
  // Tracks the last document this wrapper pushed INTO the store, so we
  // can tell external prop changes apart from the store echoing our own
  // onChange back to us.
  const lastLoadedRef = useRef<TEditorConfiguration | null>(null);
  const onChangeRef = useRef(onChange);
  onChangeRef.current = onChange;

  useEffect(() => {
    const next = document ?? EMPTY_EMAIL_MESSAGE;
    if (next !== lastLoadedRef.current) {
      lastLoadedRef.current = next;
      resetDocument(next);
    }
  }, [document]);

  useEffect(
    () =>
      subscribeToDocument((edited) => {
        lastLoadedRef.current = edited;
        onChangeRef.current(edited);
      }),
    []
  );

  const canvasSx =
    selectedScreenSize === 'mobile'
      ? {
          margin: '32px auto',
          width: 370,
          boxShadow:
            'rgba(33, 36, 67, 0.04) 0px 10px 20px, rgba(33, 36, 67, 0.04) 0px 2px 6px, rgba(33, 36, 67, 0.04) 0px 0px 1px',
        }
      : {};

  return (
    <Stack direction="row" sx={{ minHeight: 480, height: '100%' }}>
      <Stack sx={{ flex: 1, minWidth: 0 }}>
        <Stack
          direction="row"
          justifyContent="flex-end"
          sx={{ px: 1, py: 0.5, borderBottom: 1, borderColor: 'divider' }}
        >
          <ToggleButtonGroup
            size="small"
            exclusive
            value={selectedScreenSize}
            onChange={(_, value) =>
              setSelectedScreenSize(value === 'mobile' ? 'mobile' : 'desktop')
            }
          >
            <ToggleButton value="desktop">
              <Tooltip title="Desktop view">
                <MonitorOutlined fontSize="small" />
              </Tooltip>
            </ToggleButton>
            <ToggleButton value="mobile">
              <Tooltip title="Mobile view">
                <PhoneIphoneOutlined fontSize="small" />
              </Tooltip>
            </ToggleButton>
          </ToggleButtonGroup>
          <ToggleInspectorPanelButton />
        </Stack>
        <Box sx={{ flex: 1, overflow: 'auto', bgcolor: '#f5f5f5' }}>
          <Box sx={canvasSx}>
            <EditorBlock id="root" />
          </Box>
        </Box>
      </Stack>
      <InspectorDrawer />
    </Stack>
  );
};
