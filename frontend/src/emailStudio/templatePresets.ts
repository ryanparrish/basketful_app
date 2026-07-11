/**
 * "Start from…" layout presets for the Email Design Studio.
 *
 * Design-JSON documents in the Basketful email chrome (green header,
 * white card, footer) so staff never start from a blank canvas unless
 * they want to. Tokens inside Text blocks are simple {{ var }} only —
 * filters and {% %} tags belong in Html blocks (see
 * __tests__/templateTokenSurvival.test.ts).
 */
import type { TEditorConfiguration } from './EmailStudioEditor';
import { EMPTY_EMAIL_MESSAGE } from './EmailStudioEditor';

const BASKETFUL_GREEN = '#2d6a4f';

const basketfulChrome = (
  title: string,
  bodyBlocks: Record<string, unknown>,
  bodyIds: string[]
): TEditorConfiguration =>
  ({
    root: {
      type: 'EmailLayout',
      data: {
        backdropColor: '#F5F5F5',
        canvasColor: '#FFFFFF',
        textColor: '#262626',
        fontFamily: 'MODERN_SANS',
        childrenIds: ['block-header', ...bodyIds, 'block-footer'],
      },
    },
    'block-header': {
      type: 'Container',
      data: {
        style: { backgroundColor: BASKETFUL_GREEN, padding: { top: 32, bottom: 32, left: 24, right: 24 } },
        props: { childrenIds: ['block-header-logo', 'block-header-title'] },
      },
    },
    'block-header-logo': {
      type: 'Heading',
      data: {
        style: { color: '#FFFFFF', textAlign: 'center', padding: { top: 0, bottom: 4, left: 0, right: 0 } },
        props: { text: '🛒 Basketful', level: 'h2' },
      },
    },
    'block-header-title': {
      type: 'Heading',
      data: {
        style: { color: '#FFFFFF', textAlign: 'center', padding: { top: 0, bottom: 0, left: 0, right: 0 } },
        props: { text: title, level: 'h3' },
      },
    },
    ...bodyBlocks,
    'block-footer': {
      type: 'Text',
      data: {
        style: {
          color: '#9ca3af',
          fontSize: 13,
          textAlign: 'center',
          padding: { top: 24, bottom: 24, left: 24, right: 24 },
        },
        props: { text: 'Thanks,\nThe Basketful Team' },
      },
    },
  }) as TEditorConfiguration;

export interface TemplatePreset {
  key: string;
  label: string;
  description: string;
  document: TEditorConfiguration;
}

export const TEMPLATE_PRESETS: TemplatePreset[] = [
  {
    key: 'announcement',
    label: 'Announcement',
    description: 'Basketful header, a message, and a button link.',
    document: basketfulChrome(
      'A Note From the Pantry',
      {
        'block-body-text': {
          type: 'Text',
          data: {
            style: { padding: { top: 24, bottom: 8, left: 24, right: 24 } },
            props: {
              text: 'Hi {{ user.first_name }},\n\nWrite your announcement here.',
            },
          },
        },
        'block-body-button': {
          type: 'Button',
          data: {
            style: { textAlign: 'center', padding: { top: 8, bottom: 24, left: 24, right: 24 } },
            props: {
              text: 'Open Basketful',
              url: '{{ participant_frontend_url }}',
              buttonBackgroundColor: BASKETFUL_GREEN,
              buttonTextColor: '#FFFFFF',
            },
          },
        },
      },
      ['block-body-text', 'block-body-button']
    ),
  },
  {
    key: 'simple-notice',
    label: 'Simple notice',
    description: 'Basketful header and a single text section.',
    document: basketfulChrome(
      'A Quick Update',
      {
        'block-body-text': {
          type: 'Text',
          data: {
            style: { padding: { top: 24, bottom: 24, left: 24, right: 24 } },
            props: { text: 'Hi {{ user.first_name }},\n\nWrite your update here.' },
          },
        },
      },
      ['block-body-text']
    ),
  },
  {
    key: 'blank',
    label: 'Blank canvas',
    description: 'Start from nothing.',
    document: EMPTY_EMAIL_MESSAGE,
  },
];
