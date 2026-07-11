/**
 * Spike test (permanent): Django template tokens must survive
 * EmailBuilder.js rendering.
 *
 * The studio compiles the visual design to HTML client-side via
 * renderToStaticMarkup, and the backend then renders that HTML as a
 * Django template. This locks in two behaviors the studio relies on:
 *
 * 1. Simple `{{ var }}` tokens typed in Text blocks pass through with
 *    braces intact — the variable picker only offers these.
 * 2. Filter syntax with quotes (e.g. |default:"Friend") gets its quotes
 *    HTML-escaped to &quot;, which Django's lexer would misparse — this
 *    is WHY filters and {% %} tags are restricted to raw-HTML blocks or
 *    code mode. If an upgrade changes either behavior, revisit the
 *    picker rules.
 */
import { describe, expect, it } from 'vitest';
import { renderToStaticMarkup } from '@usewaypoint/email-builder';
import type { TReaderDocument } from '@usewaypoint/email-builder';

const documentWithText = (text: string): TReaderDocument => ({
  root: {
    type: 'EmailLayout',
    data: {
      childrenIds: ['block-text'],
    },
  },
  'block-text': {
    type: 'Text',
    data: {
      props: { text },
    },
  },
});

describe('Django template tokens through renderToStaticMarkup', () => {
  it('passes simple {{ var }} tokens through intact', () => {
    const html = renderToStaticMarkup(
      documentWithText('Hello {{ user.first_name }}, your number is {{ participant_customer_number }}.'),
      { rootBlockId: 'root' }
    );
    expect(html).toContain('{{ user.first_name }}');
    expect(html).toContain('{{ participant_customer_number }}');
  });

  it('HTML-escapes quotes inside filter syntax (documented limitation)', () => {
    const html = renderToStaticMarkup(
      documentWithText('Hello {{ user.first_name|default:"Friend" }}'),
      { rootBlockId: 'root' }
    );
    // Quotes become &quot; — Django would misparse this filter. The
    // variable picker therefore only offers simple tokens in Text blocks.
    expect(html).not.toContain('|default:"Friend"');
    expect(html).toContain('&quot;');
  });

  it('passes {% %} tags through an Html block untouched', async () => {
    const doc: TReaderDocument = {
      root: {
        type: 'EmailLayout',
        data: { childrenIds: ['block-html'] },
      },
      'block-html': {
        type: 'Html',
        data: {
          props: {
            contents:
              '<ul>{% for product in products %}<li>{{ product.name }}</li>{% endfor %}</ul>',
          },
        },
      },
    };
    const html = renderToStaticMarkup(doc, { rootBlockId: 'root' });
    expect(html).toContain('{% for product in products %}');
    expect(html).toContain('{{ product.name }}');
  });
});
