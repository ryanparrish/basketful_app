/**
 * Pure state helpers for the Email Design Studio page.
 *
 * Kept free of React so the mode/save semantics are unit-testable:
 * - Visual save compiles the design to HTML client-side and stamps
 *   content_source='design' for that language.
 * - Code save keeps the stored design (so users can return to it) but
 *   stamps content_source='code', marking the design stale.
 */
import { renderToStaticMarkup } from '@usewaypoint/email-builder';
import type { TEditorConfiguration } from './EmailStudioEditor';

export type StudioLanguage = 'en' | 'es';
export type StudioMode = 'visual' | 'code';

export interface LanguageDraft {
  subject: string;
  htmlContent: string;
  textContent: string;
  designJson: TEditorConfiguration | null;
  contentSource: 'design' | 'code' | null;
}

export interface EmailTypeRecordFields {
  subject_en?: string | null;
  subject_es?: string | null;
  html_content_en?: string | null;
  html_content_es?: string | null;
  text_content_en?: string | null;
  text_content_es?: string | null;
  design_json_en?: TEditorConfiguration | null;
  design_json_es?: TEditorConfiguration | null;
  content_source_en?: 'design' | 'code' | null;
  content_source_es?: 'design' | 'code' | null;
}

export const draftFromRecord = (
  record: EmailTypeRecordFields,
  language: StudioLanguage
): LanguageDraft => ({
  subject: record[`subject_${language}`] ?? '',
  htmlContent: record[`html_content_${language}`] ?? '',
  textContent: record[`text_content_${language}`] ?? '',
  designJson: record[`design_json_${language}`] ?? null,
  contentSource: record[`content_source_${language}`] ?? null,
});

/**
 * The mode a language tab should open in: Visual only when a design
 * exists and code edits haven't superseded it.
 */
export const initialModeForDraft = (draft: LanguageDraft): StudioMode =>
  draft.designJson && draft.contentSource === 'design' ? 'visual' : 'code';

/**
 * True when returning to Visual mode would show a design that is older
 * than the current code — saving from Visual would overwrite code edits.
 */
export const isDesignStale = (draft: LanguageDraft): boolean =>
  draft.designJson !== null && draft.contentSource === 'code';

export const compileDesignToHtml = (design: TEditorConfiguration): string =>
  renderToStaticMarkup(design, { rootBlockId: 'root' });

/**
 * PATCH payload for saving one language's draft. Explicit `_lang`
 * columns only — the dataProvider strips stale base fields itself.
 */
export const buildSavePayload = (
  language: StudioLanguage,
  mode: StudioMode,
  draft: LanguageDraft
): Record<string, unknown> => {
  const payload: Record<string, unknown> = {
    [`subject_${language}`]: draft.subject,
    [`text_content_${language}`]: draft.textContent,
  };
  if (mode === 'visual') {
    if (!draft.designJson) {
      throw new Error('Visual save requires a design document');
    }
    payload[`html_content_${language}`] = compileDesignToHtml(draft.designJson);
    payload[`design_json_${language}`] = draft.designJson;
    payload[`content_source_${language}`] = 'design';
  } else {
    payload[`html_content_${language}`] = draft.htmlContent;
    payload[`content_source_${language}`] = 'code';
    // design_json intentionally untouched: kept, but now stale.
  }
  return payload;
};
