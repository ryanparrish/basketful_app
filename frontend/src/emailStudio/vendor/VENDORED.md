# Vendored: EmailBuilder.js editor

Source: https://github.com/usewaypoint/email-builder-js
Path: `examples/vite-emailbuilder-mui/src` (the reference editor app)
Commit: `ce3e610749fc80d7e999b20e28f6e775bfe09da7`
License: MIT (see upstream LICENSE)

The npm packages (`@usewaypoint/email-builder`, `@usewaypoint/block-*`,
`@usewaypoint/document-core`) provide the document model, Reader, and
`renderToStaticMarkup`. The drag-and-drop **editor UI** is not published
to npm — upstream's supported integration path is copying the reference
app, which is what lives here.

## What was copied
- `documents/` — editor core (zustand store, EditorBlock, block editors,
  add-block menu, block wrappers/TuneMenu, prop schemas)
- `App/InspectorDrawer/` — the right-hand block/styles configuration panel

## What was intentionally NOT copied
- `App/SamplesDrawer/` (replaced by our VariablesPanel + template presets)
- `App/TemplatePanel/` (replaced by `../EmailStudioEditor.tsx`; upstream's
  Html/Json panels, Share/Download/Import buttons and their highlight.js +
  prettier dependencies are not needed — we have Monaco and server preview)
- `getConfiguration/` (localStorage/hash persistence), `theme.ts`, `main.tsx`

## Local modifications
1. `documents/editor/EditorContext.tsx` — no getConfiguration/localStorage;
   initializes to `EMPTY_EMAIL_MESSAGE`; added `getDocument()` and
   `subscribeToDocument()` for controlled-component integration; removed
   `samplesDrawerOpen` and `selectedMainTab` state.
2. `App/InspectorDrawer/index.tsx` — renders as an inline flex panel
   instead of a viewport-fixed MUI `Drawer`, so it nests inside the
   react-admin layout.
3. Mechanical TypeScript conformance for this repo's compiler options
   (`verbatimModuleSyntax`, `noUnusedLocals`): unused `import React`
   lines removed, type-only imports split into `import type`.

## Known deferred items
- Undo/redo: not implemented upstream; the zustand store would support a
  history stack if we want it later.

## Updating from upstream
Diff against the commit above, re-apply the three modification categories,
and re-run `npx tsc -b` + the emailStudio vitest suite (including
`templateTokenSurvival.test.ts`, which locks the `{{ }}`-passthrough
behavior the studio depends on).
