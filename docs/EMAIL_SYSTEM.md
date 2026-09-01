# Email System

> Last updated: 2026-07-13

## Overview
The Basketful email system provides a flexible, admin-configurable approach to managing transactional emails, sent through Mailgun (via [Anymail](https://anymail.dev/)). Two editing surfaces exist side by side:
- **Django Admin** (`Admin → Log → Email Types`) — a TinyMCE rich-text field for `html_content`, plus a JSON preview modal. This is the original, simpler editor.
- **Email Design Studio** (React-Admin, `frontend/src/emailStudio/`) — a Mailchimp/Unlayer-style visual block editor with a Monaco code-editor fallback, EN/ES tabs, live server-rendered preview, and a "Send test" button. This is the primary way staff edit emails today.

Both surfaces write to the same `EmailType` row; no code deployment is needed to change email content either way.

## Features

### Admin-Editable Templates
- **Email Design Studio**: drag-and-drop block editor (canvas + inspector) or raw HTML/text via Monaco, per language (English/Spanish)
- **TinyMCE** (Django admin only): rich text editor for `html_content`
- **Plain Text**: separate `text_content` field, always rendered
- **Template Variables**: Django template syntax (`{{ variable }}`), driven by a central registry (`apps/log/variables.py`) so the variable picker and preview always match what senders actually provide
- **Live Preview**: both surfaces render live via the `preview` API action — no need to save first (the studio can preview an unsaved draft)

### Email Types (seeded)
Configured via `EmailType.name` — the currently active/seeded types are:
- **`onboarding`** — new participant welcome/login-credentials email
- **`password_reset`** — password reset instructions
- **`order_window_opened`** — notifies a participant that their program's ordering window has opened
- **`low_inventory_alert`** — internal alert when products drop at/below a stock threshold
- **`order_confirmation`**, **`voucher_notification`** — seeded rows exist but are inactive placeholders; nothing in the codebase currently sends these

### Flexible Configuration
- **Database or Files**: `html_content`/`text_content` (DB) take priority over `html_template`/`text_template` (file paths), which remain as a fallback
- **Global Defaults**: the `EmailSettings` singleton (`core/models.py`) provides default from/reply-to addresses, the participant-frontend URL, and the backend domain, all overridable per-`EmailType` and all falling back to environment settings (`DEFAULT_FROM_EMAIL`, `PARTICIPANT_FRONTEND_URL`, `DOMAIN_NAME`) if unset
- **Enable/Disable**: `is_active` — inactive types are silently skipped by the send task

## Model: EmailType

### Fields

**Identification**
- `name` — slug identifier (e.g. `'onboarding'`, `'password_reset'`)
- `display_name` — human-readable name
- `is_active` — enable/disable sending

**Subject & Content** (each translated per-language — see Localization below)
- `subject` — supports template variables
- `html_content` — rich HTML content; **the send path always renders this field**, regardless of whether it was authored visually or in code
- `text_content` — plain text alternative
- `html_template` / `text_template` — fallback template file paths, used only when the content fields are empty

**Email Design Studio fields**
- `design_json` — the block-editor's document (JSON). The studio compiles this to `html_content` client-side on save.
- `content_source` — `'code'` or `'design'`; tracks whether `html_content` was last authored visually or edited directly as code (a code edit marks the stored design stale for that language)

**Email Configuration**
- `from_email` / `reply_to` — override the `EmailSettings` global defaults

**Documentation**
- `available_variables`, `description` — free-text documentation fields (the variable *picker* itself is driven by `apps/log/variables.py`, not this field)

### Template Variables

The real source of truth is `apps/log/variables.py` — a registry shared by the senders (which build the actual context) and the studio's variable picker + sample-data preview. It is **not** the `{{ user }}`/`{{ order }}` shape you might expect from an order-confirmation-style system — there is no `order`, `items`, `total`, or `site_url` variable, and `participant` is not passed as an object (its fields are flattened into named tokens instead).

Common variables (every email type):
```python
user.first_name, user.last_name, user.username, user.email   # from build_email_context()
site_name        # "Basketful"
domain           # backend domain, e.g. for password-reset links
protocol         # "http" or "https"
```

Per-type variables:
```python
# onboarding
participant_frontend_url, participant_customer_number, uid, token

# password_reset
uid, token

# order_window_opened
program_name, closes_at, participant_name, participant_customer_number, participant_frontend_url

# low_inventory_alert
products (list — loop with {% for product in products %}, product.name / product.quantity_in_stock)
threshold, product_count
```

## Admin Interface

### Location
**Admin → Log → Email Types** (Django admin) or the "Email Types" resource in React-Admin, which opens the Email Design Studio for each row.

### Django Admin Features

#### Rich Text Editor
- TinyMCE (via `tinymce.models.HTMLField`) for `html_content`

#### Preview
- A "👁️ Preview Email" button opens a modal (HTML/Plain Text tabs) that fetches `/admin/log/emailtype/<pk>/preview/` (`EmailTypeAdmin.preview_view`) and renders the saved content with sample data (`EmailType.get_sample_context_for_type()`)

#### Indicators
- ✓ Database — content stored in `html_content`/`text_content`
- 📄 File — falling back to `html_template`/`text_template`
- — — no content configured

#### Fieldsets
`TranslationAdmin` swaps `subject`/`html_content`/`text_content` for their per-language columns automatically:
1. **Basic Information** — name, display name, active status
2. **Email Content (Editable)** — html_content, text_content
3. **Fallback Template Files** — html_template, text_template (collapsed)
4. **Email Addresses** — from_email, reply_to
5. **Documentation** — available_variables, description (collapsed)
6. **Metadata** — created_at, updated_at (collapsed)

Note: `design_json`/`content_source` are **not** in the Django admin fieldsets — those are edited only through the Email Design Studio's API calls.

### Email Design Studio (React-Admin)

`frontend/src/emailStudio/EmailStudioPage.tsx` — vendored from [`email-builder-js`](https://github.com/usewaypoint/email-builder-js) (see `frontend/src/emailStudio/vendor/VENDORED.md` for exactly what was copied/modified), with a custom top toolbar, variables panel, and Monaco-based code mode built on top.

- **Top toolbar**: subject field (+ insert-variable menu), EN/ES tabs, Visual/Code toggle, preview toggle, Send test, Save
- **Left panel**: template presets ("Start from…") + the variables picker (fed by `apps/log/variables.py` via the `variables` field on the `EmailType` API serializer)
- **Center**: block canvas + inspector drawer (visual mode) or Monaco editor + plain-text box (code mode)
- **Right (optional)**: live server-rendered preview, calling the `preview` API action
- **Save semantics**: a visual-mode save compiles the block document to HTML client-side and writes both `design_json` and the compiled `html_content`; a code-mode save keeps the existing `design_json` but marks `content_source='code'` (stale) for that language. The backend always sends whatever is currently in `html_content`, regardless of source.
- **Send test**: posts to the `send-test` API action, which renders the current draft and sends a real email to the requesting staff member's own address, logged as `EmailLog(is_test=True)` so it never counts toward dedup guards or DLQ retries.

## Localization

`EmailType` is registered with `django-modeltranslation` (`apps/log/translation.py`) for `subject`, `html_content`, `text_content`, `design_json`, and `content_source` — giving each a per-language column (e.g. `subject_en`, `subject_es`) on the **same row** (not row-per-language). This matters because `has_email_been_sent()` and `retry_failed_emails()` both key dedup logic off one `EmailType` instance per name — splitting into separate rows per language would let a Spanish send bypass the English dedup guard.

At send time, `send_email_by_type()` (`apps/account/tasks/email.py`) resolves the participant's `preferred_language` (default `'en'`) and renders inside `translation.override(email_language)`, so the modeltranslation descriptors pick the right column with automatic English fallback when a translation is blank.

## Sending Emails

Emails are sent through `apps/account/tasks/email.py`, a Celery task (`send_email_by_type`) plus a few convenience wrapper tasks — not a bare `send_mail()` call:

```python
from apps.account.tasks.email import send_new_user_onboarding_email

# Dispatch async (Celery)
send_new_user_onboarding_email.delay(user.id)
```

`send_email_by_type(user_id, email_type_name, force=False, extra_context=None)`:
- Looks up the active `EmailType` by name; returns `False` silently if missing/inactive
- Skips sending if `has_email_been_sent()` already found a non-test `sent` log for this user+type (unless `force=True`)
- Builds context via `build_email_context(user)` (`user`, `domain`, `uid`, `token`, `protocol`, `site_name`) merged with any `extra_context`
- Renders subject/html/text inside `translation.override(participant.preferred_language)`
- Sends via `send_email_message()`, which wraps `EmailMultiAlternatives` + Anymail and returns the Mailgun `message_id`
- Logs an `EmailLog` row (`status='sent'` with `message_id`, or after 3 retries, `status='failed'` with `error_message`)
- Retries up to 3 times with exponential backoff (60s, 120s, 240s) on any send exception; only writes the `failed` log once retries are exhausted

Convenience wrappers, each building their own `extra_context` before delegating to `send_email_by_type`:
- `send_new_user_onboarding_email(user_id, force=False)` — adds a 24-hour dedup guard on top of the lifetime guard; injects `participant_customer_number`/`participant_frontend_url`
- `send_password_reset_email(user_id, force=False)`
- `send_order_window_opened_notification(user_id, program_name, closes_at_str, force=False)` — always calls with `force=True` since this is a recurring email; dedup for this one is owned by the caller (`apps/account/tasks/order_window.py`), not the lifetime guard
- `retry_failed_emails()` — a soft dead-letter-queue task; re-dispatches any `EmailLog` with `status='failed'`, `retry_count < 3`, created in the last 24 hours (`is_test=False`)

## Model: EmailLog

### Purpose
Track all emails sent for audit purposes, and their Mailgun delivery status.

### Fields
- `user` — FK to the recipient (there is no separate `participant` FK or `recipient` email field — the address is `user.email`)
- `email_type` — FK to `EmailType`
- `subject` — rendered subject at send time
- `status` — `sent` / `failed`
- `error_message` — if failed
- `sent_at` — auto-set timestamp
- `message_id` — Mailgun message ID (from Anymail)
- `delivery_status` — polled from Mailgun (`unknown` / `delivered` / `bounced` / `complained` / `unsubscribed` / `failed`) — see `docs/MAILGUN_DELIVERY_INTELLIGENCE.md`
- `delivery_checked_at` — last poll time
- `retry_count` — DLQ re-dispatch count
- `is_test` — true for Email Design Studio test sends

### Admin
View email history at **Admin → Log → Email Logs** (read-only) or `/api/v1/email-logs/`.

## Technical Implementation

### Files
- **apps/log/models.py** — `EmailType` and `EmailLog` models
- **apps/log/translation.py** — modeltranslation registration for per-language `EmailType` fields
- **apps/log/variables.py** — the template-variable registry (contract between senders and the studio)
- **apps/log/admin.py** — Django admin (TinyMCE + preview modal)
- **apps/log/templates/admin/log/emailtype/change_form.html** — the preview-modal template
- **apps/log/api/views.py** — `EmailTypeViewSet` (`preview`, `send-test`, `active` actions) and `EmailLogViewSet`
- **apps/account/tasks/email.py** — the actual send pipeline (Celery tasks)
- **frontend/src/emailStudio/** — the Email Design Studio UI (vendored block editor + Monaco + variables panel)
- **core/models.py** — `EmailSettings` singleton (from/reply-to defaults, participant frontend URL, backend domain)

### Rendering Methods

```python
class EmailType(models.Model):
    def render_subject(self, context_dict):
        return Template(self.subject).render(Context(context_dict))

    def render_html(self, context_dict):
        """Uses html_content if set, otherwise falls back to html_template file."""
        if self.html_content:
            return Template(self.html_content).render(Context(context_dict))
        elif self.html_template:
            return render_to_string(self.html_template, context_dict)
        return ""

    def render_text(self, context_dict):
        """Uses text_content if set, otherwise falls back to text_template file."""
        if self.text_content:
            return Template(self.text_content).render(Context(context_dict))
        elif self.text_template:
            return render_to_string(self.text_template, context_dict)
        return ""
```

### Preview API

Two preview endpoints exist:
- **Django admin**: `GET /admin/log/emailtype/<pk>/preview/` — renders the *saved* content only, used by the preview modal
- **DRF API**: `GET|POST /api/v1/email-types/<pk>/preview/` (`EmailTypeViewSet.preview`) — `GET` renders saved content, `POST` renders an unsaved draft (`subject`/`html_content`/`text_content` in the body, falling back to saved values per field), per `?language=en|es`. A `TemplateSyntaxError` returns 400 with `{detail, field}`. This is what the Email Design Studio's live preview and the "Send test" button build on.

## Backend Configuration

- **Production**: `EMAIL_BACKEND = 'anymail.backends.mailgun.EmailBackend'`, with `ANYMAIL = {'MAILGUN_API_KEY': ..., 'MAILGUN_SENDER_DOMAIN': ...}` and `DEFAULT_FROM_EMAIL` all sourced from environment variables (`core/settings.py`)
- **Development**: `EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'` (prints to console, no Mailgun call, no `message_id`)

## Benefits

### For Administrators
- ✅ Edit emails without code changes, either in Django admin (TinyMCE) or the Email Design Studio (visual/code)
- ✅ Preview before sending, including unsaved drafts
- ✅ Send a real test to yourself before publishing
- ✅ No developer dependency

### For Developers
- ✅ Centralized email sending logic (one Celery task + typed wrappers) instead of scattered `send_mail()` calls
- ✅ Consistent template variables via a single registry
- ✅ Audit logging + Mailgun delivery status tracking built in
- ✅ Easy to add new email types — add context to a sender, register the variables, seed an `EmailType` row

### For Users
- ✅ Professional branded emails, in their preferred language
- ✅ HTML and plain text versions
- ✅ Automatic retry on transient send failures

## Future Enhancements

- Email scheduling/queuing beyond the existing DLQ retry
- A/B testing support
- Open/click tracking (flagged as a privacy question in `docs/MAILGUN_DELIVERY_INTELLIGENCE.md`)
- Attachment support
- Bulk email sending
- `order_confirmation` / `voucher_notification` are seeded but still unused — either wire them up or remove the placeholders
