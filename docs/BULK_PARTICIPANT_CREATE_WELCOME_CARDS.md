# Bulk Participant Create + Welcome Cards — Implementation Plan

> **Feature:** Give pantry staff a fast, guided flow to create multiple participants
> at once, then immediately print a physical welcome card for each one — with their
> customer number (`C-BKM-7`) and login URL front and centre.
>
> **Effort:** M — estimated 3–5 focused development days
>
> **Status:** Planning — adversarial review complete, decisions recorded below

---

## Resolved Design Decisions

> These were open questions surfaced during adversarial review. Each is answered
> here before implementation begins.

### 1. What is `location.state` and why is it a problem?

`location.state` is a React Router mechanism that passes an in-memory JavaScript
object from one route to another via `navigate('/path', { state: { ... } })`. It
lives only in the browser's session history entry — it is **not persisted** to
`localStorage`, `sessionStorage`, or the server. A hard refresh (`F5`), tab
crash, OS reboot, or browser back/forward wipe it entirely.

**Decision — layered client + server fallback.** Three storage options were
considered:

| Option | Survives refresh? | Survives tab close? | Shared workstation risk? |
|--------|---|---|---|
| `location.state` | ❌ | ❌ | Low |
| `sessionStorage` ✅ chosen | ✅ | ❌ auto-clears | Low — clears on tab close |
| `localStorage` | ✅ | ✅ | ⚠️ PII lingers for next user |
| Zustand / Redux | ❌ in-memory | ❌ | Low |
| Server batch fetch | ✅ | ✅ | Low |

`localStorage` was ruled out: participant names and login numbers persisting
after the tab closes is a privacy risk on a shared pantry workstation.
`sessionStorage` auto-clears when the tab closes — the right behaviour here.

**The print page uses a three-layer fallback chain:**

```
1. location.state        → fastest, zero network (used on first render)
       ↓ missing after refresh
2. sessionStorage        → fast, zero network (survives F5, same tab)
       ↓ missing after tab close or crash
3. GET /bulk-create-batches/:batchId  → server fetch, always works
```

`bulk_create` returns a `batch_id` (UUID). The navigate call writes to
`sessionStorage` *and* passes `location.state`. The print page URL is
`/participants/welcome-cards/:batchId` so the batch ID is always in the URL
for step 3 to use if needed.

```ts
// After bulk_create succeeds — write to sessionStorage before navigating
sessionStorage.setItem(
  `bulk_batch_${result.batch_id}`,
  JSON.stringify(result.created)
);
navigate(`/participants/welcome-cards/${result.batch_id}`, {
  state: { participants: result.created, batchId: result.batch_id },
  replace: true,
});

// On PrintWelcomeCards mount
const batchId = params.batchId;
const fromState    = location.state?.participants;
const fromSession  = JSON.parse(sessionStorage.getItem(`bulk_batch_${batchId}`) ?? 'null');
const participants = fromState ?? fromSession ?? await fetchBatch(batchId);
```

`sessionStorage` entries are keyed by `batch_id` so multiple batches don't
collide. They are cleared after the print dialog is confirmed (or on tab
close automatically).

### 2. Can we serve the welcome card in Spanish (en español)?

**Decision — yes, with a language selector in the wizard.** A
`preferred_language` field is added to `Participant` (or reused if it already
exists). The print page reads `participant.preferred_language` per card and
renders from a translated template object. For launch: English + Spanish. The
card copy strings are extracted into a `CARD_COPY` map keyed by language code:

```ts
const CARD_COPY = {
  en: {
    greeting: (name: string) => `Welcome, ${name}!`,
    loginLabel: 'YOUR LOGIN NUMBER',
    loginAt: 'Log in at:',
    instruction: 'Check your email to set your password',
  },
  es: {
    greeting: (name: string) => `¡Bienvenido/a, ${name}!`,
    loginLabel: 'SU NÚMERO DE ACCESO',
    loginAt: 'Ingrese en:',
    instruction: 'Revise su correo para crear su contraseña',
  },
};
```

The intake data-entry grid (Step 1) includes a **Language** column (dropdown:
English / Español). Default: English. The card renders in the participant's
selected language. The onboarding email language is a follow-on task — for now
the email fix ships in English only, with a `TODO` comment.

### 3. Can we wrap `bulk_create` in `transaction.atomic()`?

**Decision — yes, best-effort with explicit atomic wrapping per row, not
all-or-nothing.** Wrapping the entire batch in one `atomic()` block would mean
one bad row rolls back all 20 good ones — not what staff expect. Instead:

- Each row save is wrapped in its own `transaction.atomic()` (savepoint)
- If a row raises an unexpected DB exception, that row is caught, added to
  `errors`, and the loop continues
- The signal (`initialize_participant`) fires inside the per-row savepoint — if
  user creation fails, the `Participant` row itself is also rolled back
- The response clearly reports `created` (list) and `errors` (list) so the
  frontend can show exactly which rows landed and which did not

```python
for index, row_data in enumerate(rows):
    try:
        with transaction.atomic():       # ← per-row savepoint
            row_data["create_user"] = True
            s = ParticipantCreateSerializer(data=row_data)
            if not s.is_valid():
                errors.append({"index": index, "errors": s.errors})
                continue
            participant = s.save()        # signal fires inside savepoint
            created.append({...})
    except Exception as exc:
        errors.append({"index": index, "errors": {"non_field": [str(exc)]}})
```

### 4. Is there a grace period before onboarding emails fire?

**Decision — smart threshold, inspired by HubSpot's email scheduling model:**

| Batch size | Behaviour |
|------------|-----------|
| ≤ 5 participants | `send_new_user_onboarding_email.delay()` — fires immediately (current behaviour, staff likely to catch a mistake instantly) |
| > 5 participants | `send_new_user_onboarding_email.apply_async(countdown=300)` — 5-minute hold queued against the `BulkCreateBatch` |

When a batch is in the grace period, a **cancellable batch banner** appears in
the admin (Step 4 and the participant list) with a countdown: _"Onboarding
emails send in 4:32 — Cancel"_. Clicking Cancel calls
`POST /api/v1/participants/bulk-create-batches/{batch_id}/cancel/` which
revokes all pending Celery tasks for that batch using
`AsyncResult(task_id).revoke(terminate=False)`.

This requires a new model (see §5e) and one new API action — but it transforms
an irreversible bulk operation into a recoverable one.

### 5. Other changes from adversarial review

| Finding | Decision |
|---------|----------|
| Auto `window.print()` at 500ms | **Removed.** Print fires only on explicit button click. Button gets focus on Step 4 mount. |
| Double-submit on Step 3 | **Fixed.** Button disabled + loading spinner on first click, re-enabled only on error. |
| "Remove" button label | **Renamed** to "Clear row" before submit; hidden after creation. |
| Warning banner for navigate-away | **Replaced** with React Router `useBlocker` — blocks navigation with a confirmation dialog. |
| Skipped rows silently dropped | **Fixed.** Step 4 shows two lists: "Created (N)" and "Skipped (M) — fix and re-add". |
| Step indicator | **Added** — persistent `Stepper` component (MUI) visible at every step. |
| Terminology | **Standardised** — "LOGIN NUMBER" everywhere. Login screen label change tracked as a separate ticket. |
| `bulk_create` with 0 valid rows | **Returns 400**, not 201. |
| `bulk_validate` with empty array | **Returns 400** with `"At least one row is required."` |
| `C-BKM-7` separator normalisation | **Full normalization pipeline** — see §5f for detail. The check digit algorithm and normalization function already exist in `warehouse_id.py`; they just aren't wired into the login path yet. |
| No audit log for bulk creates | **`BulkCreateBatch` IS the audit log** — `created_by`, `created_at`, participant snapshot. Register it in Django admin. Add a `ParticipantCreateLog` entry for single-participant creates too. See §5g. |
| `bulk_create` email abuse / no rate limit | **Yes, this is a real risk.** Add `ScopedRateThrottle` (`20/hour` per user) on `bulk_create`. Add email deduplication guard (skip if onboarding email sent in last 24 h). See §5h. |

---

## Table of Contents

1. [Problem Statement](#1-problem-statement)
2. [What We're Building](#2-what-were-building)
3. [Pre-requisite: Fix the Onboarding Email](#3-pre-requisite-fix-the-onboarding-email)
4. [Architecture Overview](#4-architecture-overview)
5. [Backend Changes](#5-backend-changes)
6. [Frontend Changes](#6-frontend-changes)
7. [Data Migration](#7-data-migration)
8. [File Checklist](#8-file-checklist)
9. [Implementation Order](#9-implementation-order)
10. [Edge Cases & Guard Rails](#10-edge-cases--guard-rails)
11. [Testing Plan](#11-testing-plan)

---

## 1. Problem Statement

### Current pain points

| Pain | Root cause |
|------|------------|
| Staff create participants one-at-a-time | `ParticipantCreate` has no bulk path |
| Print output is a plain table | `PrintCustomerList` doesn't have a card layout |
| Onboarding email says `YOUR USERNAME: jane-smith-hope` | Participants log in with `C-BKM-7` — they have never seen or used a username |
| Staff have no physical artefact to hand to participants at intake | No welcome card feature exists |

### What participants need at the end of intake

1. Their **customer number** (`C-BKM-7`) — the only credential they use at the login screen
2. The **URL** to the participant app
3. A **link to set their password** (already sent via email, but the email currently gives the wrong credential)

---

## 2. What We're Building

### The user journey

```
Staff sit down at a computer with a stack of paper intake forms
                        ↓
Open "Bulk Create Participants" wizard
                        ↓
Step 1: Enter participant rows (name, email, program, household size)
                        ↓
Step 2: Review — see validation errors per row, flag duplicate emails
                        ↓
Step 3: Confirm — creates all valid participants + user accounts + queues onboarding emails
                        ↓
Step 4: Print Welcome Cards — one card per participant, auto-opens print dialog
                        ↓
Staff cut and hand cards to participants
```

### The welcome card (physical output)

Each card shows:
- Org logo + name
- Participant name
- `YOUR LOGIN NUMBER: C-BKM-7` (large, bold)
- `Log in at: [participant app URL]`
- Brief instruction: "Check your email to set your password"

---

## 3. Pre-requisite: Fix the Onboarding Email

**This ships first, independently. It is a one-migration change.**

### The bug

The `onboarding` `EmailType` record (seeded in `apps/log/migrations/0005_seed_email_types.py`)
contains:

```
YOUR USERNAME: {{ user.username }}
```

Participants **cannot** log in with a username. They use their customer number (`C-BKM-7`).
The `FlexibleTokenObtainPairSerializer` in `apps/account/api/jwt_serializers.py` resolves
`C-XXX-D → Participant → User` — the username is a backend artifact only.

### The fix

New migration: `apps/log/migrations/0010_fix_onboarding_email_customer_number.py`

Replace the broken credential line with the correct one in both `text_content` and
`html_content`, and add the login URL.

**Text content change:**

```
Before:
========================================
YOUR USERNAME: {{ user.username }}
========================================
(Save this - you'll need it to log in)

Set your password here:
{{ protocol }}://{{ domain }}{% url 'password_reset_confirm' uidb64=uid token=token %}

After:
========================================
YOUR LOGIN NUMBER: {{ participant_customer_number }}
========================================
Keep this — you'll type it in to log in.

Log in at:
{{ protocol }}://{{ participant_frontend_url }}/login

First-time setup — set your password:
{{ protocol }}://{{ domain }}{% url 'password_reset_confirm' uidb64=uid token=token %}
```

**HTML content change:** Same content restructure, with the customer number in a
large `<div>` styled like a badge, and the login URL as a clickable `<a>` tag.

### New email context variables

Two new variables need to be injected in `apps/account/tasks/email.py` inside
`send_new_user_onboarding_email`:

```python
# In the existing email context builder, add:
"participant_customer_number": participant.customer_number,
"participant_frontend_url": settings.PARTICIPANT_FRONTEND_URL,  # new env var
```

Add `PARTICIPANT_FRONTEND_URL` to `core/settings.py` reading from env:

```python
PARTICIPANT_FRONTEND_URL = os.environ.get("PARTICIPANT_FRONTEND_URL", "https://app.basketful.org")
```

---

## 4. Architecture Overview

```
frontend/src/pages/BulkParticipantCreate.tsx   ← new wizard page (4 steps)
frontend/src/pages/PrintWelcomeCards.tsx        ← new print page
frontend/src/resources/participants.tsx         ← "Bulk Create" toolbar button
frontend/src/AdminApp.tsx                       ← 2 new routes registered

apps/account/models.py                          ← new BulkCreateBatch model
apps/account/api/views.py                       ← bulk_create, bulk_validate, batch cancel
apps/account/api/serializers.py                 ← BulkParticipantCreateSerializer
apps/account/tasks/email.py                     ← add customer_number context
core/settings.py                                ← PARTICIPANT_FRONTEND_URL env var
apps/log/migrations/0010_fix_onboarding_email   ← fix wrong credential
```

One new model (`BulkCreateBatch`). The existing `initialize_participant` signal
handles user creation. Email dispatch timing is now controlled by batch size
(≤5 → immediate, >5 → 5-minute countdown with cancel window).

---

## 5. Backend Changes

### 5a. `apps/account/api/serializers.py`

Add a `BulkParticipantCreateSerializer` below the existing `ParticipantCreateSerializer`:

```python
class BulkParticipantCreateSerializer(serializers.Serializer):
    """Serializer for bulk participant creation — wraps a list of participant dicts."""

    participants = ParticipantCreateSerializer(many=True)

    def validate_participants(self, value):
        if not value:
            raise serializers.ValidationError("At least one participant is required.")
        if len(value) > 100:
            raise serializers.ValidationError("Maximum 100 participants per batch.")
        return value
```

The inner `ParticipantCreateSerializer` already covers all validation.
`create_user` defaults to `True` in the view (not the serializer) so the wizard
eualways creates login accounts — no checkbox confusion.

### 5b. `apps/account/api/views.py` — new `bulk_create` action

Add to `ParticipantViewSet`, alongside the existing bulk actions:

```python
import uuid
from django.db import transaction
from celery.result import AsyncResult
from apps.account.tasks.email import send_new_user_onboarding_email

EMAIL_EAGER_THRESHOLD = 5   # ≤ this many → send immediately; > this → 5-min hold
EMAIL_GRACE_SECONDS   = 300  # 5 minutes


@action(detail=False, methods=["post"], url_path="bulk-create")
def bulk_create(self, request):
    """
    Create multiple participants at once with login accounts.

    Accepts:
        { "participants": [ { name, email, program, adults, children,
                               preferred_language, ... }, ... ] }

    Returns a per-row result array that mirrors the input 1-to-1.
    Every input row has a result entry at the same index.

        {
          "batch_id": "<uuid>",
          "email_grace_seconds": 300 | 0,
          "summary": { "created": 8, "failed": 2 },
          "rows": [
            {
              "index": 0,
              "status": "created",           # or "failed"
              "participant": {
                "id": 42,
                "name": "Jane Smith",
                "email": "jane@example.com",
                "customer_number": "C-BKM-7",
                "preferred_language": "en",
                "program_name": "Go Fresh"
              },
              "errors": null
            },
            {
              "index": 1,
              "status": "failed",
              "participant": null,
              "errors": { "email": ["A participant with this email already exists."] }
            },
            ...
          ]
        }

    rows.length always equals len(input participants).
    The frontend derives created/failed lists by filtering rows on status.
    The BulkCreateBatch snapshot stores only the rows where status=="created".
    """
    serializer = BulkParticipantCreateSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    rows = serializer.validated_data["participants"]
    if not rows:
        return Response(
            {"detail": "At least one participant row is required."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    result_rows       = []   # one entry per input row, at the same index
    deferred_task_ids = []
    use_grace         = len(rows) > EMAIL_EAGER_THRESHOLD

    for index, row_data in enumerate(rows):
        try:
            with transaction.atomic():          # per-row savepoint
                row_data["create_user"] = True
                row_data["_skip_onboarding_signal"] = use_grace

                row_serializer = ParticipantCreateSerializer(data=row_data)
                if not row_serializer.is_valid():
                    # Validation failure — record at this index, continue loop
                    result_rows.append({
                        "index":       index,
                        "status":      "failed",
                        "participant": None,
                        "errors":      row_serializer.errors,
                    })
                    continue

                participant = row_serializer.save()

                if use_grace and participant.user_id:
                    task = send_new_user_onboarding_email.apply_async(
                        kwargs={"user_id": participant.user.id},
                        countdown=EMAIL_GRACE_SECONDS,
                    )
                    deferred_task_ids.append(task.id)

                result_rows.append({
                    "index":  index,
                    "status": "created",
                    "participant": {
                        "id":                 participant.id,
                        "name":               participant.name,
                        "email":              participant.email,
                        "customer_number":    participant.customer_number,
                        "preferred_language": participant.preferred_language,
                        "program_name":       participant.program.name if participant.program else "",
                    },
                    "errors": None,
                })
        except Exception as exc:
            result_rows.append({
                "index":       index,
                "status":      "failed",
                "participant": None,
                "errors":      {"non_field": [str(exc)]},
            })

    created_rows = [r for r in result_rows if r["status"] == "created"]

    if not created_rows:
        return Response(
            {
                "detail": "No participants could be created.",
                "rows":   result_rows,
                "summary": {"created": 0, "failed": len(result_rows)},
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Persist only the created participants for print-page recovery
    batch = BulkCreateBatch.objects.create(
        created_by=request.user,
        participants=[r["participant"] for r in created_rows],
        celery_task_ids=deferred_task_ids,
        email_grace_seconds=EMAIL_GRACE_SECONDS if use_grace else 0,
    )

    return Response(
        {
            "batch_id":            str(batch.id),
            "email_grace_seconds": EMAIL_GRACE_SECONDS if use_grace else 0,
            "summary": {
                "created": len(created_rows),
                "failed":  len(result_rows) - len(created_rows),
            },
            "rows": result_rows,   # 1-to-1 with input; frontend filters by status
        },
        status=status.HTTP_201_CREATED,
    )


@action(detail=True, methods=["post"], url_path="cancel",
        queryset=BulkCreateBatch.objects.all())
def cancel_bulk_batch(self, request, pk=None):
    """Revoke queued onboarding emails for a grace-period batch."""
    batch = get_object_or_404(BulkCreateBatch, id=pk, created_by=request.user)
    revoked = 0
    for task_id in batch.celery_task_ids:
        AsyncResult(task_id).revoke(terminate=False)
        revoked += 1
    batch.cancelled = True
    batch.save(update_fields=["cancelled"])
    return Response({"revoked": revoked})
```

> **Note on `_skip_onboarding_signal`:** The `initialize_participant` signal
> currently calls `.delay()` unconditionally. Add a guard:
> `if not getattr(instance, '_skip_onboarding_signal', False):` before the
> `.delay()` call in `signals.py`. When `use_grace` is True, the view
> calls `.apply_async(countdown=...)` itself.

### 5c. `apps/account/models.py` — new `BulkCreateBatch` model

Add below the existing models. No new app needed — lives in `account`.

```python
import uuid
from django.db import models
from django.contrib.auth.models import User


class BulkCreateBatch(models.Model):
    """Records a single bulk participant creation event.

    Serves two purposes:
    1. Recovery — the print page can re-fetch participant data if
       location.state is lost (tab refresh, crash).
    2. Cancellation — stores Celery task IDs so queued onboarding emails
       can be revoked during the grace period.
    """
    id                = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_by        = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at        = models.DateTimeField(auto_now_add=True)
    participants      = models.JSONField()          # snapshot of created[] list
    celery_task_ids   = models.JSONField(default=list)  # task IDs for cancellation
    email_grace_seconds = models.IntegerField(default=0)
    cancelled         = models.BooleanField(default=False)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Bulk Create Batch"
```

Requires a new migration: `apps/account/migrations/XXXX_add_bulk_create_batch.py`.

Add a `BulkCreateBatch` retrieve endpoint to `ParticipantViewSet` so the print
page can recover:

```python
@action(detail=False, methods=["get"], url_path="bulk-create-batches/(?P<batch_id>[^/.]+)")
def get_bulk_batch(self, request, batch_id=None):
    batch = get_object_or_404(BulkCreateBatch, id=batch_id)
    return Response({
        "batch_id":   str(batch.id),
        "created":    batch.participants,
        "cancelled":  batch.cancelled,
        "email_grace_seconds": batch.email_grace_seconds,
        "created_at": batch.created_at.isoformat(),
    })
```

### 5d. `apps/account/tasks/email.py`

Inside `send_new_user_onboarding_email` (the existing Celery task), add
`participant_customer_number` and `participant_frontend_url` to the context dict
passed to the template renderer:

```python
# Existing context will have: user, domain, protocol, uid, token
# Add:
from django.conf import settings
try:
    participant = user.participant
    participant_customer_number = participant.customer_number or ""
except Exception:
    participant_customer_number = ""

context.update({
    "participant_customer_number": participant_customer_number,
    "participant_frontend_url": settings.PARTICIPANT_FRONTEND_URL,
})
```

### 5e. `core/settings.py`

```python
# Participant frontend URL — used in onboarding emails and welcome cards
PARTICIPANT_FRONTEND_URL = os.environ.get(
    "PARTICIPANT_FRONTEND_URL", "https://app.basketful.org"
)
```

Add `PARTICIPANT_FRONTEND_URL` to `.env.example` and `render.yaml` environment
variable list.

---

### 5f. `apps/account/utils/warehouse_id.py` + `apps/account/api/jwt_serializers.py` — input normalization

**Why this matters.** `validate_customer_number()` and the DB lookup in
`FlexibleTokenObtainPairSerializer` both require literal ASCII hyphen (U+002D).
A participant who types their number from a printed card can fail silently if:

| What they type | What goes wrong |
|----------------|-----------------|
| `C–BKM–7` | En-dash (U+2013) — iPhone/Mac autocorrect replaces `--` |
| `C—BKM—7` | Em-dash (U+2014) |
| `C BKM 7` | Spaces instead of hyphens |
| `CBKM7` | No separator at all |
| `c-bkm-7` | Lowercase — currently handled by `.upper()` |
| `C-BKM- 7` | Space before check digit |

**The algorithm.** The check digit is a weighted modulo-10 sum. From
`warehouse_id.py`:

```
code = "BKM"
B=0 (0th in SAFE_CHARS), K=7, M=8
weighted sum = (0×3) + (7×2) + (8×1) = 22
check digit  = (10 - 22%10) % 10 = 8    ← C-BKM-8, not C-BKM-7 (just an example)
```

The `calculate_check_digit()` and `validate_customer_number()` functions already
exist and are correct. They just aren't used at login time.

**The fix — add `normalize_customer_number()` to `warehouse_id.py`:**

```python
import unicodedata

# Unicode code points for dash variants → canonical ASCII hyphen
_DASH_CHARS = {
    '\u2013',  # en-dash    –
    '\u2014',  # em-dash    —
    '\u2012',  # figure-dash ‒
    '\u2212',  # minus sign  −
    '\u00AD',  # soft hyphen (invisible)
}

def normalize_customer_number(raw: str) -> str:
    """
    Normalise a user-typed customer number to canonical C-XXX-D format.

    Handles: en-dash, em-dash, spaces-as-separators, no separator,
             lowercase, leading/trailing whitespace.

    Returns the normalised string for DB lookup — does NOT validate it.
    Call validate_customer_number() after this if you need hard validation.
    """
    s = raw.strip().upper()

    # Replace Unicode dash variants with ASCII hyphen
    for dash in _DASH_CHARS:
        s = s.replace(dash, '-')

    # Remove internal spaces (handles "C BKM 7" and "C-BKM- 7")
    s = s.replace(' ', '')

    # Handle no-separator form: CBKM7 → C-BKM-7
    # Pattern: C followed by exactly 3 SAFE_CHARS followed by 1 digit
    import re
    no_sep = re.match(r'^C([BCDFGHJKMNPRTVWXY]{3})(\d)$', s)
    if no_sep:
        s = f"C-{no_sep.group(1)}-{no_sep.group(2)}"

    return s
```

**Wire it into `FlexibleTokenObtainPairSerializer`** — replace the current
`identifier.upper()` lookup with:

```python
from apps.account.utils.warehouse_id import normalize_customer_number, validate_customer_number

# Instead of:
#   participant = Participant.objects.get(customer_number=identifier.upper())

normalized = normalize_customer_number(identifier)
is_valid, reason = validate_customer_number(normalized)
if not is_valid:
    raise AuthenticationFailed({
        'detail': f'Invalid login number format. {reason}',
        'code': 'invalid_customer_number_format'
    })
participant = Participant.objects.select_related('user').get(
    customer_number=normalized
)
```

This surfaces a meaningful error (e.g. _"Check digit mismatch: expected 8, got 7"_)
instead of the confusing _"Customer number not found"_ when a participant
miscopies the last digit.

**Also print the check digit on the card clearly.** The current card spec shows
`C-BKM-7` in a monospace-like badge. Add a small footnote line below the badge
(screen only, hidden at print):
> _"If you can't log in, make sure you typed every character exactly, including the number at the end."_

**Files changed:** `apps/account/utils/warehouse_id.py` (add `normalize_customer_number`),
`apps/account/api/jwt_serializers.py` (call normalize + validate before DB lookup).

---

### 5g. Audit log for participant creates

**Why `BulkCreateBatch` alone is insufficient.** Single-participant creates
(through `ParticipantCreate` in the admin frontend or the Django admin) leave no
record of which staff member created them or when. The existing `apps/log` app
has `BaseLog`, `VoucherLog`, and `UserLoginLog` — there is no `ParticipantCreateLog`.

**The `BulkCreateBatch` model IS an audit trail for bulk creates** — it stores
`created_by`, `created_at`, and a JSON snapshot of created participants.
It just needs to be:
1. Registered in Django admin with useful `list_display`
2. Covered by a data retention policy
3. Extended to cover single-participant creates too

**Changes:**

**a. Register `BulkCreateBatch` in `apps/account/admin.py`:**

```python
@admin.register(BulkCreateBatch)
class BulkCreateBatchAdmin(admin.ModelAdmin):
    list_display  = ['id', 'created_by', 'created_at', 'participant_count', 'cancelled']
    list_filter   = ['cancelled', 'created_at']
    readonly_fields = ['id', 'created_by', 'created_at', 'participants',
                       'celery_task_ids', 'email_grace_seconds', 'cancelled']
    search_fields = ['created_by__username']

    def participant_count(self, obj):
        return len(obj.participants)
    participant_count.short_description = 'Created'
```

**b. Write a thin log entry for single-participant creates.** Rather than a new
model, the `ParticipantCreate` `onSuccess` callback sends a lightweight
`POST /api/v1/participants/log-create/` action that records:

```json
{ "participant_id": 42, "created_by": "staff-username", "created_at": "ISO8601" }
```

This can be stored in `BulkCreateBatch` with `participants = [single snapshot]`
and `email_grace_seconds = 0` — the same model, no schema change needed.
The view sets `batch_size=1` implicitly.

**c. Data retention.** Add a `TODO` comment in `BulkCreateBatch`:
> _"Retention: `participants` JSON contains PII (names + emails). Consider
> purging after 90 days or replacing with a count-only summary after staff
> confirm cards were printed."_

**Files changed:** `apps/account/admin.py` (register model),
`apps/account/api/views.py` (single-create log endpoint or inline in existing
`create` action).

---

### 5h. Email abuse — rate limit on `bulk_create`

**Yes, this should concern you.** The threat model has two actors:

| Actor | Scenario | Realistic? |
|-------|----------|------------|
| Accidental staff error | Paste a 500-row CSV twice | High |
| Disgruntled/malicious staff | Send spam onboarding emails to arbitrary addresses | Low, but irreversible |
| External attacker | `bulk_create` requires `IsAuthenticated` — attacker needs a staff JWT first | Low |

The existing `LoginRateThrottle` (`5/minute`) protects the login endpoint but
has no bearing on `bulk_create`.

**Mitigations — add all three:**

**1. `ScopedRateThrottle` on `bulk_create`** — add to `settings.py`:

```python
REST_FRAMEWORK = {
    ...
    'DEFAULT_THROTTLE_RATES': {
        ...
        'bulk_create': '20/hour',   # per authenticated user
    }
}
```

And on the view action:

```python
from rest_framework.throttling import ScopedRateThrottle

@action(detail=False, methods=["post"], url_path="bulk-create")
def bulk_create(self, request):
    self.throttle_scope = 'bulk_create'
    ...
```

20 batches/hour allows a staff member to work through a large intake event
(400+ participants in batches of 25) without hitting the limit, while
making a runaway loop visible within minutes.

**2. Email deduplication guard in `send_new_user_onboarding_email`** — before
dispatching, check whether an onboarding email was already sent to this user
in the last 24 hours:

```python
from apps.log.models import EmailLog
from django.utils import timezone

already_sent = EmailLog.objects.filter(
    user=user,
    email_type__slug='onboarding',
    sent_at__gte=timezone.now() - timedelta(hours=24),
).exists()
if already_sent:
    logger.info("Skipping duplicate onboarding email for user %s", user.id)
    return
```

This is idempotency — a retry, a re-run, or a malicious duplicate batch cannot
re-send the email within the 24-hour window.

**3. Cap already in plan (100 rows/batch)** — the serializer validation already
limits each batch to 100 rows. Combined with the `20/hour` throttle, worst-case
is 2,000 emails per hour per staff account — still too many if abused, but the
throttle makes the 20th batch wait until the window resets, giving an incident
window of 1 hour before a suspicious pattern would be visible in `EmailLog`.

**Files changed:** `core/settings.py` (throttle rate),
`apps/account/api/views.py` (`throttle_scope` on `bulk_create`),
`apps/account/tasks/email.py` (deduplication guard).

### 6a. `frontend/src/pages/BulkParticipantCreate.tsx` — **new file**

A 4-step wizard, modelled on the existing `BulkVoucherCreate.tsx` pattern.

#### Step structure

| Step | Screen | Primary action |
|------|--------|----------------|
| 1 | Data entry grid | Add/remove rows |
| 2 | Validation preview | Review errors, fix or skip invalid rows |
| 3 | Confirm | "Create X participants" button |
| 4 | Print welcome cards | Auto-opens print dialog |

#### Step 1 — Data entry grid

- MUI `Table` with one editable row per participant (using controlled `<TextField>` cells)
- Columns: **Name**, **Email**, **Program** (dropdown), **Adults**, **Children**, **Language** (EN / ES)
- The **Program** dropdown is populated live from `GET /api/v1/programs/` — it shows exactly the program names configured in the admin, not hard-coded labels. If the label on a paper intake form doesn't match the dropdown option, that is a data-entry configuration issue, not a code issue. To mitigate confusion at intake:
  - The dropdown renders the `display_name` (or `name`) field from the API, matching whatever the pantry coordinator has configured
  - A **ℹ️ tooltip** on the column header reads: _"Select the program shown on the participant's intake form. If you don't see the right program, ask your coordinator to add it in Settings → Programs."_
  - The Step 2 validation preview shows the resolved program name next to each row so staff can spot mismatches before confirming
- "Add Another Person" button appends a blank row (label makes clear it does *not* save)
- "Clear row" icon on each row (renamed from "Remove" — does not delete from DB)
- "Paste from clipboard" stretch goal (deferred)
- Default: start with **1** blank row (not 3 — avoids pressure to fill unused rows)
- Persistent MUI `<Stepper>` visible at the top of every step

```tsx
// Minimal row shape
interface IntakeRow {
  id: string;               // local UUID for React key
  name: string;
  email: string;
  program: number | '';
  adults: number;
  children: number;
  preferred_language: 'en' | 'es';  // default 'en'
}
```

#### Step 2 — Validation preview

- POST to `/api/v1/participants/bulk-create/` with `?dry_run=true`
  (or a separate `/bulk-validate/` action — see design decision below)
- Show a summary: "X valid, Y have errors"
- Per-row status chip: ✅ Ready / ⚠️ Error
- Inline error text under each problem field
- "Back to edit" button returns to Step 1 with errors highlighted **and moves
  programmatic focus to the first field containing an error** — keyboard users
  and screen reader users must not have to Tab through all preceding cells to
  reach the first problem. Implement by storing `{ rowIndex, fieldName }` of
  the first error in state and calling `.focus()` on that input ref after
  the step transition completes (`useEffect` on step change).

> **Design decision — dry run vs. separate validate endpoint:**
> The simplest approach is a `bulk-validate` action that runs the same serializer
> validation but does **not** save. This avoids a `dry_run` query param and is
> consistent with how the existing `BulkVoucherCreate` preview step works (it
> calls a separate `preview/` endpoint). Add:
>
> ```python
> @action(detail=False, methods=["post"], url_path="bulk-validate")
> def bulk_validate(self, request):
>     serializer = BulkParticipantCreateSerializer(data=request.data)
>     serializer.is_valid(raise_exception=True)
>     rows = serializer.validated_data["participants"]
>     errors = []
>     for i, row in enumerate(rows):
>         s = ParticipantCreateSerializer(data={**row, "create_user": True})
>         if not s.is_valid():
>             errors.append({"index": i, "errors": s.errors})
>     return Response({"errors": errors, "valid_count": len(rows) - len(errors)})
> ```

#### Step 3 — Confirm

- Read-only name list so staff can do a final visual check against paper forms
- Summary: "You are about to create N participants. Each will receive an onboarding email with their login number and a link to set their password."
- Single large "Create Participants" button
  - **Disabled + loading spinner immediately on first click** (prevents double-submit)
  - Re-enabled only if the request returns an error
- On success → navigate to Step 4, replacing history entry (`replace: true`) and passing `batch_id` + created participants via `location.state`

The frontend derives its two lists by filtering `rows` on `status`:

```ts
const createdParticipants = result.rows
  .filter(r => r.status === 'created')
  .map(r => r.participant!);

const failedRows = result.rows
  .filter(r => r.status === 'failed');
// failedRows[n].index maps back to the original input row at that position
// failedRows[n].errors contains field-level messages to highlight in Step 2
```

Step 4 shows two sections: **"Created (N)"** (card grid) and **"Could not create (M)"**
listing the failed rows by name with their error so staff know exactly who to
re-add. The `index` field means the UI can also highlight those rows if staff
click "Go back and fix".

> **Grace period banner:** If `email_grace_seconds > 0` in the response, Step 4
> shows: _"Onboarding emails send in 5:00 — [Cancel Emails]"_ with a live
> countdown. "Cancel Emails" calls the batch cancel endpoint.

#### Step 4 — Print welcome cards

- Navigate to `/participants/welcome-cards/:batchId` (URL contains `batch_id`)
- Pass `participants` via `location.state` as a fast path
- If `location.state` is missing (refresh / crash), fetch from
  `GET /api/v1/participants/bulk-create-batches/:batchId/`
- **`window.print()` is NOT called automatically.** Focus moves to the
  "Print Welcome Cards" button on mount. Staff click to trigger print.
- Navigation away is blocked on two levels:
  1. **In-app navigation** (clicking a React-Admin menu link, browser back button within the SPA): React Router `useBlocker` intercepts and shows a confirmation dialog: _"Welcome cards have not been printed. Leave anyway?"_
  2. **Tab/window close or address-bar navigation** (typing a new URL, closing the tab, `Cmd+W`): `useBlocker` does not fire for these. Register `window.addEventListener('beforeunload', handler)` on mount and remove it after the print button is clicked or the user confirms leaving. The `beforeunload` handler sets `event.preventDefault()` which triggers the browser's native "Leave site?" prompt.

  ```tsx
  // Mount both guards together
  const hasNotPrinted = useRef(true);

  // Guard 1: in-app navigation
  useBlocker(() => hasNotPrinted.current
    ? !window.confirm('Welcome cards have not been printed. Leave anyway?')
    : false
  );

  // Guard 2: tab close / external navigation
  useEffect(() => {
    const handler = (e: BeforeUnloadEvent) => {
      if (hasNotPrinted.current) e.preventDefault();
    };
    window.addEventListener('beforeunload', handler);
    return () => window.removeEventListener('beforeunload', handler);
  }, []);
  ```

  Both guards are cleared (by setting `hasNotPrinted.current = false`) when the
  staff member clicks "Print Welcome Cards" or explicitly confirms leaving.

```tsx
// After successful creation:
navigate(`/participants/welcome-cards/${result.batch_id}`, {
  state: { participants: result.created, batchId: result.batch_id },
  replace: true,   // prevents back-button re-submission
});
```

---

### 6b. `frontend/src/pages/PrintWelcomeCards.tsx` — **new file**

Receives `participants` from `location.state` **or** fetches from
`/api/v1/participants/bulk-create-batches/:batchId/` if state is missing.
Renders a bilingual card grid. Print is triggered by an explicit button click.

```tsx
const PARTICIPANT_URL = import.meta.env.VITE_PARTICIPANT_URL ?? 'https://app.basketful.org';

interface WelcomeParticipant {
  id: number;
  name: string;
  customer_number: string;
  email: string;
  preferred_language: 'en' | 'es';
  program_name: string;
}

// Card copy by language
const CARD_COPY = {
  en: {
    greeting: (name: string) => `Welcome, ${name}!`,
    loginLabel: 'YOUR LOGIN NUMBER',
    loginAt: 'Log in at:',
    instruction: 'Check your email to set your password',
  },
  es: {
    greeting: (name: string) => `¡Bienvenido/a, ${name}!`,
    loginLabel: 'SU NÚMERO DE ACCESO',
    loginAt: 'Ingrese en:',
    instruction: 'Revise su correo para crear su contraseña',
  },
};
```

The print button receives `autoFocus` so keyboard users can trigger print
immediately without tabbing. `window.print()` is called inside a click
handler — ensuring it is always a user-gesture-initiated call, which prevents
browser popup-policy blocking.

#### Card layout (per participant)

**Name rendering rules:**
- Display the name exactly as entered — no reformatting, no assumed first/last split.
  `participant.name` is a single free-text field; the card prints it verbatim.
- Truncate at 40 characters with an ellipsis if the name overflows the card
  width at the chosen font size. Flag truncated names in the on-screen preview
  with a ⚠️ tooltip: _"Name was shortened to fit the card — edit the participant
  record to adjust."_
- Font size for the greeting scales down automatically:
  - ≤ 20 chars → 16pt
  - 21–32 chars → 13pt
  - 33–40 chars → 11pt
- Diacritical characters (`é`, `ñ`, `ș`, etc.) must render correctly — use a
  web-safe font stack with Unicode coverage (e.g. `system-ui, sans-serif`), not
  a decorative font that may lack glyphs.

```
┌─────────────────────────────────────────┐
│  [ORG LOGO]   Love Your Neighbor        │
├─────────────────────────────────────────┤
│  ¡Bienvenido/a, José Martínez-López!    │  ← verbatim, scaled to fit
│                                         │
│  SU NÚMERO DE ACCESO                    │  ← language-aware label
│  ┌─────────────────────────────────┐    │
│  │  C-BKM-7                        │    │  ← 48px bold, Atkinson Hyperlegible
│  └─────────────────────────────────┘    │
│                                         │
│  Ingrese en:                            │
│  pantry.basketful.app                   │
│                                         │
│  Revise su correo para crear su         │
│  contraseña                             │
└─────────────────────────────────────────┘
```

#### Print CSS

```css
@media print {
  /* Hide the React-Admin chrome */
  header, nav, aside, .RaSidebar-root,
  .RaAppBar-root, .no-print { display: none !important; }

  /*
   * 2-up card grid on letter paper.
   *
   * DOM ORDER NOTE: Cards are rendered sequentially in the DOM
   * (card 1 complete, then card 2 complete, etc.) — never interleaved.
   * The CSS grid places them visually 2-up but the reading order for
   * screen readers and keyboard navigation is always card 1 → card 2 → card 3.
   * Do NOT use CSS order property or visual-only reordering.
   */
  .card-grid {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 0.25in;
    padding: 0.5in;
  }

  .welcome-card {
    border: 2px solid #000;
    border-radius: 8px;
    padding: 0.2in;
    break-inside: avoid;        /* modern spec — replaces page-break-inside */
    page-break-inside: avoid;   /* legacy fallback */
    /* Ensure content inset ≥ 10mm from card edge to survive printer margins */
    box-sizing: border-box;
  }

  .customer-number-badge {
    font-size: 36pt;
    font-weight: 900;
    /* Atkinson Hyperlegible: better than monospace for dyslexia and I/l/1 distinction */
    font-family: 'Atkinson Hyperlegible', system-ui, sans-serif;
    letter-spacing: 0.12em;
    border: 3px solid #000;
    padding: 8px 16px;
    display: inline-block;
    margin: 8px 0;
    /*
     * ARIA: The badge element in JSX must carry aria-label so screen readers
     * announce full context, not just the raw token.
     * <div class="customer-number-badge"
     *      aria-label={`Your login number: ${participant.customer_number}`}>
     *   {participant.customer_number}
     * </div>
     *
     * Without aria-label, NVDA/VoiceOver reads "C dash B K M dash 7" with no
     * indication of what the number is for.
     */
  }

  /*
   * PRINTER MARGIN SAFETY
   * OS printer drivers impose a non-printable border (typically 0.25–0.5in).
   * @page margin reserves space outside the card grid so content never sits
   * inside the driver's clip zone. The .card-grid padding (0.5in) then
   * provides additional inset so card borders never touch the page edge.
   */
  @page {
    margin: 0.75in;
    size: letter;
  }
}

@media screen {
  /*
   * Responsive single-column layout on screen.
   * At 400% zoom a 2-up grid would overflow the viewport — use single column
   * on screen so the preview is always readable regardless of zoom level.
   * Staff don't need to see 2-up on screen; they just need to verify card
   * content before clicking Print.
   */
  .card-grid {
    display: flex;
    flex-direction: column;
    gap: 16px;
    padding: 24px;
    max-width: 480px;   /* keeps cards readable at any zoom */
  }
  .welcome-card {
    border: 2px solid #333;
    border-radius: 8px;
    padding: 24px;
  }
}
```

> **Why single-column on screen?** At 400% browser zoom a `repeat(2, 1fr)` grid
> will overflow the viewport with no scroll indicator. Using `flex-direction:
> column` on screen means the print preview is always readable. The 2-up layout
> only applies `@media print` where the browser controls the physical page size.

#### Screen-only toolbar

```
[← Back to Participants]  [Print Welcome Cards (N)]  [Print All]
```

> **Shared network printer risk.** `window.print()` opens the OS print dialog,
> which pre-selects the system default printer. On a shared workstation this is
> often a network printer used by multiple departments. Fifty welcome cards sent
> to the wrong device before staff notice is a real scenario.
>
> Mitigation — show a persistent **orange alert banner** on the print page
> (above the card grid, not dismissible until print is clicked):
> _"⚠️ Before printing: confirm the correct printer is selected in the print
> dialog. Welcome cards contain participant login numbers."_
>
> The banner disappears after `window.print()` is called. It cannot prevent a
> wrong printer selection — that is an OS-level choice — but it creates a
> deliberate pause before staff click OK in the print dialog.

---

### 6c. `frontend/src/resources/participants.tsx`

Add a **"Bulk Create"** button to the `ParticipantList` top toolbar, alongside
the existing "Create" button:

```tsx
// In ParticipantListActions or the <TopToolbar> of ParticipantList:
<Button
  component={Link}
  to="/participants/bulk-create"
  label="Bulk Create"
  startIcon={<GroupAddIcon />}
/>
```

### Single-participant create path

`ParticipantCreate` is currently a bare `<SimpleForm>` with no `create_user`
field exposed and no post-save redirect to the print page. After this plan
ships, single-participant creation should behave consistently with bulk:

**Changes to `ParticipantCreate`:**
1. Add a `BooleanInput source="create_user"` toggle (default `true` — staff
   almost always want a login account at intake)
2. Use React-Admin's `<Create mutationOptions={{ onSuccess }}>` callback to
   redirect to `/participants/welcome-cards` after save, passing the new
   participant as a single-item array via `sessionStorage` (same pattern as
   bulk — no `batch_id` needed for a single record, just write directly):

```tsx
const onSuccess = (participant: WelcomeParticipant) => {
  if (participant.customer_number) {
    sessionStorage.setItem(
      `single_participant_card`,
      JSON.stringify([participant])
    );
    navigate(`/participants/welcome-cards/single`);
  } else {
    // No user account created — go to show page as normal
    navigate(`/participants/${participant.id}/show`);
  }
};
```

**Email delay:** A single participant is always ≤5 rows, so `create_user`
fires `.delay()` immediately via the existing signal — no grace period, no
cancel window needed.

**`PrintWelcomeCards` at `/participants/welcome-cards/single`:** Reads from
`sessionStorage.getItem('single_participant_card')` — same component, no
server fetch needed since there's no `batch_id` in the URL.

Also add **"Print Welcome Card"** to `ParticipantShow` actions — for when
staff need to reprint a card for an existing participant:

```tsx
// In ParticipantShowActions:
<Button
  label="Print Welcome Card"
  onClick={() => navigate(`/participants/welcome-cards`, {
    state: { participants: [{ ...record }] }
  })}
  startIcon={<PrintIcon />}
/>
```

---

### 6d. `frontend/src/AdminApp.tsx`

Register the two new routes in `<CustomRoutes>`:

```tsx
import BulkParticipantCreate from './pages/BulkParticipantCreate';
import PrintWelcomeCards from './pages/PrintWelcomeCards';

// Inside <CustomRoutes>:
<Route path="/participants/bulk-create" element={<BulkParticipantCreate />} />
<Route path="/participants/welcome-cards" element={<PrintWelcomeCards />} />
```

---

### 6e. `frontend/.env` / `frontend/.env.production`

Add the participant frontend URL env var so welcome cards show the right link:

```
# .env (local development)
VITE_PARTICIPANT_URL=http://localhost:5173

# .env.production
VITE_PARTICIPANT_URL=https://pantry.basketful.app
```

---

## 7. Data Migration

**File:** `apps/log/migrations/0010_fix_onboarding_email_customer_number.py`

```python
from django.db import migrations

NEW_TEXT_CONTENT = '''Welcome to Basketful, {{ user.first_name|default:"Friend" }}!

{{ site_name }} — Life Skills Program

We're excited to have you join our community!

========================================
YOUR LOGIN NUMBER: {{ participant_customer_number }}
========================================
Keep this — you'll type it in every time you log in.

Step 1 — Set your password:
{{ protocol }}://{{ domain }}{% url 'password_reset_confirm' uidb64=uid token=token %}

This link expires in 3 days. If it has expired, ask pantry staff to resend.

Step 2 — Log in at:
{{ participant_frontend_url }}/login

Step 3 — Place your first order!

Questions? Reply to this email or speak to your pantry coordinator.

— The {{ site_name }} Team
'''

# HTML content follows the same structure but with styling.
# Update the key line in the existing HTML:
#   Before: <p class="username-box">YOUR USERNAME: {{ user.username }}</p>
#   After:  <p class="username-box">YOUR LOGIN NUMBER: {{ participant_customer_number }}</p>
# And add:  <p>Log in at: <a href="{{ participant_frontend_url }}/login">{{ participant_frontend_url }}/login</a></p>

def fix_onboarding_email(apps, schema_editor):
    EmailType = apps.get_model('log', 'EmailType')
    try:
        onboarding = EmailType.objects.get(name='onboarding')
        onboarding.text_content = NEW_TEXT_CONTENT
        # Update just the critical lines in the HTML rather than replacing the whole block
        html = onboarding.html_content
        html = html.replace(
            'YOUR USERNAME: {{ user.username }}',
            'YOUR LOGIN NUMBER: {{ participant_customer_number }}'
        )
        html = html.replace(
            '✓ Sign in to your account',
            '✓ Log in at <strong>{{ participant_frontend_url }}/login</strong>'
        )
        onboarding.html_content = html
        onboarding.available_variables = (
            onboarding.available_variables
            + ', {{ participant_customer_number }}, {{ participant_frontend_url }}'
        )
        onboarding.save()
    except EmailType.DoesNotExist:
        pass  # Nothing to migrate in a fresh environment


def reverse_fix(apps, schema_editor):
    pass  # One-way fix; reverting would re-introduce a bug


class Migration(migrations.Migration):

    dependencies = [
        ('log', '0009_emaillog_delivery_status'),
    ]

    operations = [
        migrations.RunPython(fix_onboarding_email, reverse_fix),
    ]
```

---

## 8. File Checklist

### New files

- [ ] `frontend/src/pages/BulkParticipantCreate.tsx`
- [ ] `frontend/src/pages/PrintWelcomeCards.tsx`
- [ ] `apps/log/migrations/0010_fix_onboarding_email_customer_number.py`
- [ ] `apps/account/migrations/XXXX_add_bulk_create_batch.py`

### Modified files

| File | Change |
|------|--------|
| `frontend/src/resources/participants.tsx` | Add "Bulk Create" toolbar button; add "Print Welcome Card" to Show actions |
| `frontend/src/AdminApp.tsx` | Register 2 new routes (now with `:batchId` param) |
| `frontend/.env` | Add `VITE_PARTICIPANT_URL` |
| `frontend/.env.production` | Add `VITE_PARTICIPANT_URL` |
| `apps/account/models.py` | Add `BulkCreateBatch` model |
| `apps/account/api/serializers.py` | Add `BulkParticipantCreateSerializer` (add `preferred_language` field) |
| `apps/account/api/views.py` | Add `bulk_create`, `bulk_validate`, `get_bulk_batch`, `cancel_bulk_batch` |
| `apps/account/signals.py` | Add `_skip_onboarding_signal` guard before `.delay()` call |
| `apps/account/tasks/email.py` | Add `participant_customer_number` + `participant_frontend_url` to email context; add 24h deduplication guard |
| `apps/account/models.py` (Participant) | Add `preferred_language` field (CharField, choices `en`/`es`, default `en`) |
| `apps/account/admin.py` | Register `BulkCreateBatch` with audit-friendly `list_display` |
| `apps/account/utils/warehouse_id.py` | Add `normalize_customer_number()` function |
| `apps/account/api/jwt_serializers.py` | Call `normalize_customer_number()` + `validate_customer_number()` before DB lookup |
| `core/settings.py` | Add `PARTICIPANT_FRONTEND_URL` env var; add `bulk_create` throttle rate (`20/hour`) |
| `render.yaml` | Add `PARTICIPANT_FRONTEND_URL` env var entry |

---

## 9. Implementation Order

Work in this order to ship value incrementally and keep PRs reviewable:

### PR 1 — Fix the email (ships first, standalone, no frontend)
1. Add `PARTICIPANT_FRONTEND_URL` to `core/settings.py`
2. Update `apps/account/tasks/email.py` to inject `participant_customer_number` + `participant_frontend_url`
3. Write and run `0010_fix_onboarding_email_customer_number.py`
4. **Test:** Create a test participant with `create_user=True`, check email log shows customer number

### PR 2 — Backend bulk create endpoints
1. Add `preferred_language` to `Participant` model + migration
2. Add `BulkCreateBatch` model + migration
3. Add `BulkParticipantCreateSerializer` to `serializers.py`
4. Add `bulk_validate` action to `ParticipantViewSet`
5. Add `bulk_create` action (with atomic per-row savepoints + smart email delay)
6. Add `get_bulk_batch` and `cancel_bulk_batch` actions
7. Add `_skip_onboarding_signal` guard in `signals.py`
8. **Test:** `pytest apps/account/tests/` — add tests for all endpoints including cancel and recovery

### PR 3 — Frontend wizard + print page
1. Create `PrintWelcomeCards.tsx`
2. Create `BulkParticipantCreate.tsx` (Steps 1–4)
3. Register routes in `AdminApp.tsx`
4. Add toolbar button + show action in `participants.tsx`
5. Add env vars to `.env` and `.env.production`
6. **Test:** Manual walkthrough — create 3 participants, verify cards print correctly

---

## 10. Edge Cases & Guard Rails

| Scenario | Handling |
|----------|----------|
| Participant types en-dash or spaces in login number | `normalize_customer_number()` in `FlexibleTokenObtainPairSerializer` converts to canonical form before lookup; check digit validation gives specific error if the digit itself is wrong |
| Participant copies wrong check digit | `validate_customer_number()` returns `"Check digit mismatch: expected 8, got 7"` — surfaced as `invalid_customer_number_format` error code |
| Staff sends duplicate batch (same emails twice) | 24h deduplication guard in `send_new_user_onboarding_email` skips resend; `bulk_create` `ScopedRateThrottle` (`20/hour`) limits burst |
| No record of who created a participant | `BulkCreateBatch` stores `created_by` + participant snapshot for all bulk creates; single creates also write a 1-row `BulkCreateBatch` entry via `onSuccess` callback |
| Participant already exists (same email) | Serializer raises `ValidationError` — surfaces in Step 2 with message: "A participant with this email already exists" |
| Email send fails (Celery down) | Onboarding email is best-effort; `bulk_create` still returns 201. Staff can resend via existing "Resend Onboarding Email" bulk action |
| `participant_customer_number` missing in email context | `try/except` in the task returns `""` — email sends without the number rather than crashing |
| `/participants/welcome-cards/:batchId` loaded with no `location.state` | Fetch from `GET /api/v1/participants/bulk-create-batches/:batchId/`; show spinner while loading; show error if batch not found |
| Staff navigates away before printing (in-app) | React Router `useBlocker` intercepts and shows a confirmation dialog: _"Welcome cards have not been printed. Leave anyway?"_ |
| Staff closes tab / types new URL before printing | `window.addEventListener('beforeunload')` fires the browser's native "Leave site?" prompt; guard cleared after print button clicked |
| Wrong printer selected in OS print dialog | Orange non-dismissible banner above card grid warns staff to verify printer before clicking OK in the dialog |
| Program label on paper form doesn't match dropdown | Dropdown is populated live from API and reflects admin-configured names exactly; ℹ️ tooltip on column header directs staff to Settings → Programs if name is missing |
| Screen reader announces C-BKM-7 without context | `.customer-number-badge` element carries `aria-label="Your login number: {customer_number}"` so NVDA/VoiceOver announces the full phrase |
| Printer driver clips card edges (non-printable margin) | `@page { margin: 0.75in }` reserves outer margin; `.card-grid` has `padding: 0.5in` — content inset is always ≥ 0.2in from any card border, well inside printable zone |
| Very large batch (>50 rows) | Cap at 100 in serializer validation; show a persistent warning chip at 50+ in the Step 1 toolbar |
| Program not selected on a row | `program` is required; surfaces in Step 2 with message: "Please select a program" |
| `bulk_create` called with 0 valid rows | Returns **400** with `{"detail": "No participants could be created.", "errors": [...]}` |
| `bulk_validate` called with empty array | Returns **400** with `{"detail": "At least one row is required."}` |
| Double-click on Step 3 submit | Button disabled on first click; spinner shown; re-enabled only on error |
| Browser back after Step 3 success | `replace: true` on navigate removes Step 3 from history stack — back button goes to participant list, not Step 3 |
| Onboarding email grace period — staff cancels | `POST .../cancel/` revokes all Celery task IDs stored in `BulkCreateBatch`; banner updates to "Emails cancelled" |
| Staff on A4 printer | Print CSS uses `@page { size: auto }` with relative card sizing; documented limitation that Letter gives best results |

---

## 11. Testing Plan

### Backend (pytest)

```python
# apps/account/tests/test_bulk_participant_create.py

class TestBulkParticipantCreate:
    def test_bulk_validate_returns_errors_for_missing_email(self): ...
    def test_bulk_validate_returns_errors_for_duplicate_email(self): ...
    def test_bulk_create_creates_participants_and_users(self): ...
    def test_bulk_create_queues_onboarding_emails(self): ...
    def test_bulk_create_returns_customer_numbers(self): ...
    def test_bulk_create_skips_invalid_rows_and_reports_errors(self): ...
    def test_bulk_create_enforces_100_row_limit(self): ...

class TestOnboardingEmailContext:
    def test_email_context_includes_customer_number(self): ...
    def test_email_context_includes_participant_frontend_url(self): ...
```

### Frontend (Vitest)

```tsx
// frontend/src/pages/PrintWelcomeCards.test.tsx

test('renders a card for each participant', () => { ... })
test('shows empty state when no participants in location.state', () => { ... })
test('displays customer number prominently', () => { ... })
```

### Manual QA checklist

- [ ] Create 1 participant via single create form → onboarding email shows customer number
- [ ] Create 3 participants via bulk create → all receive emails with customer numbers
- [ ] Bulk create with one invalid row → Step 2 shows the error inline; valid rows proceed
- [ ] Step 4 prints 2-up card grid on letter paper — cards don't split across pages
- [ ] "Print Welcome Card" from ParticipantShow → single card prints correctly
- [ ] Navigate to `/participants/welcome-cards` with no state → empty state shown

---

## Related Docs

- [CUSTOMER_NUMBER_SYSTEM.md](CUSTOMER_NUMBER_SYSTEM.md)
- [EMAIL_SYSTEM.md](EMAIL_SYSTEM.md)
- [SIGNALS_AUTOMATION.md](SIGNALS_AUTOMATION.md)
- [BULK_VOUCHER_CREATION.md](BULK_VOUCHER_CREATION.md) — wizard pattern to follow
