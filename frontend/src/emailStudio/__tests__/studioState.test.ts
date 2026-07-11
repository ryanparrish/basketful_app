/**
 * Unit tests for the studio's mode/save semantics (studioState.ts).
 */
import { describe, expect, it } from 'vitest';
import {
  buildSavePayload,
  compileDesignToHtml,
  draftFromRecord,
  initialModeForDraft,
  isDesignStale,
  type LanguageDraft,
} from '../studioState';
import { EMPTY_EMAIL_MESSAGE } from '../EmailStudioEditor';
import type { TEditorConfiguration } from '../EmailStudioEditor';

const designWithText = (text: string): TEditorConfiguration => ({
  root: { type: 'EmailLayout', data: { childrenIds: ['t'] } },
  t: { type: 'Text', data: { props: { text } } },
});

const baseDraft = (overrides: Partial<LanguageDraft> = {}): LanguageDraft => ({
  subject: 'Hello',
  htmlContent: '<p>old html</p>',
  textContent: 'plain',
  designJson: null,
  contentSource: null,
  ...overrides,
});

describe('draftFromRecord', () => {
  it('reads per-language columns with empty-string defaults', () => {
    const draft = draftFromRecord(
      {
        subject_es: 'Hola',
        html_content_es: '<p>hola</p>',
        design_json_es: EMPTY_EMAIL_MESSAGE,
        content_source_es: 'design',
      },
      'es'
    );
    expect(draft.subject).toBe('Hola');
    expect(draft.designJson).toBe(EMPTY_EMAIL_MESSAGE);
    expect(draft.contentSource).toBe('design');
    expect(draft.textContent).toBe('');
  });
});

describe('initialModeForDraft', () => {
  it('opens Visual only when a design exists and is the content source', () => {
    expect(
      initialModeForDraft(baseDraft({ designJson: EMPTY_EMAIL_MESSAGE, contentSource: 'design' }))
    ).toBe('visual');
    expect(initialModeForDraft(baseDraft({ designJson: EMPTY_EMAIL_MESSAGE, contentSource: 'code' }))).toBe('code');
    expect(initialModeForDraft(baseDraft())).toBe('code');
  });
});

describe('isDesignStale', () => {
  it('is stale only when a design exists but code was edited after', () => {
    expect(isDesignStale(baseDraft({ designJson: EMPTY_EMAIL_MESSAGE, contentSource: 'code' }))).toBe(true);
    expect(isDesignStale(baseDraft({ designJson: EMPTY_EMAIL_MESSAGE, contentSource: 'design' }))).toBe(false);
    expect(isDesignStale(baseDraft({ contentSource: 'code' }))).toBe(false);
  });
});

describe('buildSavePayload', () => {
  it('visual save compiles the design and stamps content_source=design', () => {
    const design = designWithText('Hi {{ user.first_name }}');
    const payload = buildSavePayload('en', 'visual', baseDraft({ designJson: design }));
    expect(payload.content_source_en).toBe('design');
    expect(payload.design_json_en).toBe(design);
    expect(payload.html_content_en).toContain('{{ user.first_name }}');
    expect(payload.subject_en).toBe('Hello');
    // Never touches the other language.
    expect(Object.keys(payload).every(key => !key.endsWith('_es'))).toBe(true);
  });

  it('visual save without a design throws', () => {
    expect(() => buildSavePayload('en', 'visual', baseDraft())).toThrow();
  });

  it('code save keeps the html, stamps code, and leaves design untouched', () => {
    const payload = buildSavePayload('es', 'code', baseDraft({ htmlContent: '<p>edited</p>' }));
    expect(payload.html_content_es).toBe('<p>edited</p>');
    expect(payload.content_source_es).toBe('code');
    expect('design_json_es' in payload).toBe(false);
  });
});

describe('compileDesignToHtml', () => {
  it('produces a full email document', () => {
    const html = compileDesignToHtml(designWithText('Body text'));
    expect(html).toContain('Body text');
    expect(html.toLowerCase()).toContain('<!doctype html');
  });
});
