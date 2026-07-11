/**
 * VENDORED + ADAPTED from usewaypoint/email-builder-js.
 * Local modification: renders as an inline right-hand panel (Box) instead
 * of a viewport-fixed MUI Drawer, so it nests inside the react-admin
 * layout rather than overlaying it. See ../../VENDORED.md.
 */
import { Box, Tab, Tabs } from '@mui/material';

import { setSidebarTab, useInspectorDrawerOpen, useSelectedSidebarTab } from '../../documents/editor/EditorContext';

import ConfigurationPanel from './ConfigurationPanel';
import StylesPanel from './StylesPanel';

export const INSPECTOR_DRAWER_WIDTH = 320;

export default function InspectorDrawer() {
  const selectedSidebarTab = useSelectedSidebarTab();
  const inspectorDrawerOpen = useInspectorDrawerOpen();

  const renderCurrentSidebarPanel = () => {
    switch (selectedSidebarTab) {
      case 'block-configuration':
        return <ConfigurationPanel />;
      case 'styles':
        return <StylesPanel />;
    }
  };

  if (!inspectorDrawerOpen) return null;

  return (
    <Box
      sx={{
        width: INSPECTOR_DRAWER_WIDTH,
        flexShrink: 0,
        borderLeft: 1,
        borderColor: 'divider',
        display: 'flex',
        flexDirection: 'column',
        minHeight: 0,
      }}
    >
      <Box sx={{ height: 49, borderBottom: 1, borderColor: 'divider' }}>
        <Box px={2}>
          <Tabs value={selectedSidebarTab} onChange={(_, v) => setSidebarTab(v)}>
            <Tab value="styles" label="Styles" />
            <Tab value="block-configuration" label="Inspect" />
          </Tabs>
        </Box>
      </Box>
      <Box sx={{ flex: 1, overflow: 'auto' }}>
        {renderCurrentSidebarPanel()}
      </Box>
    </Box>
  );
}
