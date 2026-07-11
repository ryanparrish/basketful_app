/**
 * VENDORED + ADAPTED from usewaypoint/email-builder-js
 * (examples/vite-emailbuilder-mui/src/documents/editor/EditorContext.tsx).
 *
 * Local modifications (see ../../../VENDORED.md):
 * - Document initializes to EMPTY_EMAIL_MESSAGE instead of reading
 *   window.location.hash / localStorage via getConfiguration.
 * - Added getDocument()/subscribeToDocument() so the host page can
 *   observe edits (controlled-component integration).
 * - samplesDrawer state removed (the host app renders its own left panel).
 * - selectedMainTab state removed (the host app owns preview/code tabs).
 */
import { create } from 'zustand';

import type { TEditorConfiguration } from './core';

export const EMPTY_EMAIL_MESSAGE: TEditorConfiguration = {
  root: {
    type: 'EmailLayout',
    data: {
      backdropColor: '#F5F5F5',
      canvasColor: '#FFFFFF',
      textColor: '#262626',
      fontFamily: 'MODERN_SANS',
      childrenIds: [],
    },
  },
};

type TValue = {
  document: TEditorConfiguration;

  selectedBlockId: string | null;
  selectedSidebarTab: 'block-configuration' | 'styles';
  selectedScreenSize: 'desktop' | 'mobile';

  inspectorDrawerOpen: boolean;
};

const editorStateStore = create<TValue>(() => ({
  document: EMPTY_EMAIL_MESSAGE,
  selectedBlockId: null,
  selectedSidebarTab: 'styles',
  selectedScreenSize: 'desktop',

  inspectorDrawerOpen: true,
}));

export function useDocument() {
  return editorStateStore((s) => s.document);
}

export function useSelectedBlockId() {
  return editorStateStore((s) => s.selectedBlockId);
}

export function useSelectedScreenSize() {
  return editorStateStore((s) => s.selectedScreenSize);
}

export function useSelectedSidebarTab() {
  return editorStateStore((s) => s.selectedSidebarTab);
}

export function useInspectorDrawerOpen() {
  return editorStateStore((s) => s.inspectorDrawerOpen);
}

export function setSelectedBlockId(selectedBlockId: TValue['selectedBlockId']) {
  const selectedSidebarTab = selectedBlockId === null ? 'styles' : 'block-configuration';
  const options: Partial<TValue> = {};
  if (selectedBlockId !== null) {
    options.inspectorDrawerOpen = true;
  }
  return editorStateStore.setState({
    selectedBlockId,
    selectedSidebarTab,
    ...options,
  });
}

export function setSidebarTab(selectedSidebarTab: TValue['selectedSidebarTab']) {
  return editorStateStore.setState({ selectedSidebarTab });
}

export function resetDocument(document: TValue['document']) {
  return editorStateStore.setState({
    document,
    selectedSidebarTab: 'styles',
    selectedBlockId: null,
  });
}

export function setDocument(document: TValue['document']) {
  const originalDocument = editorStateStore.getState().document;
  return editorStateStore.setState({
    document: {
      ...originalDocument,
      ...document,
    },
  });
}

export function getDocument() {
  return editorStateStore.getState().document;
}

/**
 * Host-app integration: subscribe to document edits. Returns an
 * unsubscribe function. The callback fires on every document change.
 */
export function subscribeToDocument(
  callback: (document: TEditorConfiguration) => void
) {
  let previous = editorStateStore.getState().document;
  return editorStateStore.subscribe((state) => {
    if (state.document !== previous) {
      previous = state.document;
      callback(state.document);
    }
  });
}

export function toggleInspectorDrawerOpen() {
  const inspectorDrawerOpen = !editorStateStore.getState().inspectorDrawerOpen;
  return editorStateStore.setState({ inspectorDrawerOpen });
}

export function setSelectedScreenSize(selectedScreenSize: TValue['selectedScreenSize']) {
  return editorStateStore.setState({ selectedScreenSize });
}
