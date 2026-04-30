# Mailgun Delivery Intelligence — Architecture Doc

> **Status**: Future milestone — not yet built.
> This document describes the "Wild" evolution of the [Medium] Mailgun delivery status feature.
> The Medium build (polling + `delivery_status` field) must be complete before beginning this work.

---

## What This Is

The Medium build answers: *"Did Mailgun accept this email?"*

This architecture answers: *"Can we actually reach this participant — and what should we do when we can't?"*

It reframes `EmailLog` from a passive audit trail into an **active participant reachability engine**. Real-time Mailgun webhook events feed a delivery event timeline. A denormalized reachability score per participant enables a staff dashboard for identifying who can't be reached. Undelivered emails trigger automatic escalation. And every email Basketful sends is mirrored into a participant-facing inbox — so participants who never receive the email can still read it inside the app.

---

## Architecture Overview

```
Mailgun sends webhook → anymail validates HMAC → Django signal fires
         ↓
  process_delivery_event (Celery task)
         ↓
  CommunicationEvent row created (idempotent)
         ↓
  recompute_reachability_score (Celery task)   ←→  ParticipantReachabilityScore
         ↓
  [if bounced] escalate_undelivered (Celery beat countdown task)

React-Admin polls /api/communication-events/?email_log=<id>
  → DeliveryEventTimeline in EmailLogShow
  → ReachabilityDashboard (aggregate stats + unreachable participant list)

Participant frontend polls /api/messages/
  → InboxPage (read-only mirror of sent email content)
```

---

## New Data Models

### `CommunicationEvent`

Stores each individual Mailgun tracking event (one email can have many events: `accepted` → `delivered`, or `accepted` → `bounced`).

```python
class CommunicationEvent(models.Model):
    """
    One row per Mailgun tracking event for a sent email.
    idempotent: unique on (email_log, event_type, timestamp).
    """
    EVENT_TYPES = [
        ("accepted",     "Accepted"),
        ("delivered",    "Delivered"),
        ("bounced",      "Bounced"),
        ("complained",   "Complained"),
        ("unsubscribed", "Unsubscribed"),
        ("opened",       "Opened"),
        ("clicked",      "Clicked"),
        ("failed",       "Failed"),
    ]

    email_log    = models.ForeignKey("log.EmailLog", on_delete=models.CASCADE,
                                     related_name="events")
    event_type   = models.CharField(max_length=20, choices=EVENT_TYPES)
    timestamp    = models.DateTimeField()
    recipient    = models.EmailField(blank=True)
    reject_reason = models.CharField(max_length=255, blank=True)
    esp_name     = models.CharField(max_length=50, default="mailgun")
    created_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("email_log", "event_type", "timestamp")]
        ordering = ["-timestamp"]
```

### `CommunicationMessage`

Stores the rendered email body at send time, linked from `EmailLog`. Enables the participant inbox even when Mailgun drops the email.

```python
class CommunicationMessage(models.Model):
    """
    Immutable snapshot of an email's content at send time.
    Linked from EmailLog. Enables the participant inbox.
    """
    email_log    = models.OneToOneField("log.EmailLog", on_delete=models.CASCADE,
                                        related_name="message_snapshot")
    thread_id    = models.UUIDField(default=uuid.uuid4, db_index=True)
    subject      = models.CharField(max_length=255)
    body_html    = models.TextField()
    body_text    = models.TextField()
    created_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
```

> **Why `thread_id`?** It's a no-op today but makes future two-way threading non-breaking.
> Staff replies or participant → staff messages can share the same `thread_id` without a schema migration.

### `ParticipantReachabilityScore`

One row per participant. Denormalized so the dashboard can filter with a single indexed query instead of aggregating all events at request time.

```python
class ParticipantReachabilityScore(models.Model):
    """
    Denormalized delivery health score for a participant.
    Updated by Celery task after each new CommunicationEvent.
    Score: 0 (completely unreachable) to 100 (fully reachable).
    """
    participant       = models.OneToOneField("account.Participant",
                                              on_delete=models.CASCADE,
                                              related_name="reachability")
    score             = models.IntegerField(default=100, db_index=True)
    last_delivery     = models.DateTimeField(null=True, blank=True)
    hard_bounce_count = models.IntegerField(default=0)
    complaint_count   = models.IntegerField(default=0)
    last_updated      = models.DateTimeField(auto_now=True)
    flagged_for_review = models.BooleanField(default=False, db_index=True)

    class Meta:
        ordering = ["score"]
```

---

## New Celery Tasks

### `process_delivery_event`

```python
@shared_task(bind=True, max_retries=3)
def process_delivery_event(self, message_id, event_type, recipient,
                            timestamp, reject_reason, esp_name):
    """
    Idempotently record a Mailgun tracking event and trigger downstream.
    Called from the anymail.signals.tracking signal handler.
    """
    try:
        log = EmailLog.objects.get(message_id=message_id)
    except EmailLog.DoesNotExist:
        # Mailgun webhook may fire before our DB write completes
        raise self.retry(countdown=10)

    CommunicationEvent.objects.update_or_create(
        email_log=log,
        event_type=event_type,
        timestamp=timestamp,
        defaults={"recipient": recipient, "reject_reason": reject_reason or ""},
    )

    # Update the fast-path delivery_status on EmailLog too (Medium field)
    terminal = {"delivered", "bounced", "complained", "unsubscribed", "failed"}
    if event_type in terminal:
        EmailLog.objects.filter(pk=log.pk).update(delivery_status=event_type)

    # Recompute reachability score for this participant
    if log.user_id:
        recompute_reachability_score.delay(log.user_id)

    # Schedule escalation if bounced
    if event_type == "bounced":
        escalate_undelivered.apply_async(
            args=[log.id],
            countdown=settings.DELIVERY_ESCALATION_TTL_HOURS * 3600,
        )
```

### `recompute_reachability_score`

Runs after every event for a user. Calculates score from recent delivery history and updates `ParticipantReachabilityScore`.

```python
@shared_task
def recompute_reachability_score(user_id):
    from django.contrib.auth import get_user_model
    User = get_user_model()
    try:
        user = User.objects.select_related("participant").get(pk=user_id)
        participant = user.participant
    except (User.DoesNotExist, AttributeError):
        return

    window = timezone.now() - timedelta(days=90)
    recent_logs = EmailLog.objects.filter(user=user, sent_at__gte=window)
    total = recent_logs.count()
    bounces = recent_logs.filter(delivery_status="bounced").count()
    complaints = recent_logs.filter(delivery_status="complained").count()

    if total == 0:
        score = 100
    else:
        # Simple weighted score; tune weights as data accumulates
        penalty = min(100, (bounces * 40) + (complaints * 20))
        score = max(0, 100 - penalty)

    flagged = score < 40 or bounces >= 2

    ParticipantReachabilityScore.objects.update_or_create(
        participant=participant,
        defaults={
            "score": score,
            "hard_bounce_count": bounces,
            "complaint_count": complaints,
            "flagged_for_review": flagged,
            "last_updated": timezone.now(),
        },
    )
```

### `escalate_undelivered`

```python
@shared_task
def escalate_undelivered(email_log_id):
    """
    If an email is still not delivered after DELIVERY_ESCALATION_TTL_HOURS,
    flag the participant for manual staff outreach.
    """
    try:
        log = EmailLog.objects.select_related("user__participant").get(pk=email_log_id)
    except EmailLog.DoesNotExist:
        return

    if log.delivery_status == "delivered":
        return  # Already delivered — no escalation needed

    participant = getattr(getattr(log.user, "participant", None), None)
    if participant:
        ParticipantReachabilityScore.objects.filter(
            participant=participant
        ).update(flagged_for_review=True)
        logger.warning(
            "[Escalation] Participant %s flagged for manual outreach — "
            "email_log_id=%s delivery_status=%s",
            participant.id, email_log_id, log.delivery_status
        )
```

---

## Webhook Setup

### Django signal handler (`apps/log/signals.py`)

```python
from anymail.signals import tracking
from django.dispatch import receiver
from .tasks.logs import process_delivery_event

@receiver(tracking)
def handle_mailgun_tracking_event(sender, event, esp_name, **kwargs):
    """
    Fires for every Mailgun delivery event.
    Side-effect free — delegates immediately to Celery.
    """
    process_delivery_event.delay(
        message_id=event.message_id,
        event_type=event.event_type.name,
        recipient=event.recipient or "",
        timestamp=event.timestamp.isoformat() if event.timestamp else None,
        reject_reason=getattr(event, "reject_reason", None),
        esp_name=esp_name,
    )
```

### URL registration (`core/urls.py`)

```python
from anymail.webhooks import AnymailWebhookView

urlpatterns += [
    path("webhooks/mailgun/", AnymailWebhookView.as_view(), name="anymail-webhook"),
]
```

### Required setting

```python
# core/settings.py — add to ANYMAIL dict
ANYMAIL = {
    ...
    "MAILGUN_WEBHOOK_SIGNING_KEY": env("MAILGUN_WEBHOOK_SIGNING_KEY"),
}
```

> anymail validates Mailgun's HMAC signature automatically — no custom verification code needed.
> Register the webhook URL in the Mailgun dashboard: `https://<your-domain>/webhooks/mailgun/`

---

## New API Endpoints

| Endpoint | ViewSet | Notes |
|---|---|---|
| `GET /api/communication-events/` | `CommunicationEventViewSet` | Read-only, staff. Filter by `email_log`. |
| `GET /api/participant-reachability/` | `ParticipantReachabilityViewSet` | Read-only, staff. Filter by `flagged_for_review`, `score__lt`. |
| `GET /api/messages/` | `CommunicationMessageViewSet` | Read-only. Participants see only their own messages. |

---

## React-Admin Changes

### `DeliveryEventTimeline` (new component)

Appears inside `EmailLogShow`. Queries `/api/communication-events/?email_log=<id>` and renders a MUI `<Timeline>` — one node per event, color-coded.

```tsx
// Example event timeline entry
const EVENT_COLOR = {
  delivered:    'success',
  bounced:      'error',
  complained:   'warning',
  accepted:     'info',
  opened:       'success',
  clicked:      'success',
  unsubscribed: 'default',
};
```

### `ReachabilityDashboard` (new resource page)

- **Summary cards**: total emails sent (30 days), delivery rate %, bounce rate %, complaint rate %
- **Filterable list**: participants with `flagged_for_review=true`, sortable by `score`
- **Quick action**: "Mark reviewed" button clears the `flagged_for_review` flag

---

## Participant Frontend Changes

### `InboxPage` (`participant-frontend/src/pages/InboxPage.tsx`)

A new `/inbox` route. Uses `useQuery` (TanStack Query, same pattern as the rest of the participant frontend) to fetch `/api/messages/`. Renders a list of message subjects with timestamps; clicking opens the full `body_html` in a sandboxed `<iframe>` or stripped plain text.

> **Privacy note**: The inbox shows only messages sent to the currently authenticated participant. No cross-user visibility.

---

## Settings Required

```python
# core/settings.py
DELIVERY_ESCALATION_TTL_HOURS = env.int("DELIVERY_ESCALATION_TTL_HOURS", default=48)

ANYMAIL = {
    "MAILGUN_API_KEY": env("MAILGUN_API_KEY"),
    "MAILGUN_SENDER_DOMAIN": env("MAILGUN_SENDER_DOMAIN", default="mg.lovewm.org"),
    "MAILGUN_WEBHOOK_SIGNING_KEY": env("MAILGUN_WEBHOOK_SIGNING_KEY"),  # ← new
}
```

---

## Phased Rollout

| Phase | What ships | Prerequisite |
|---|---|---|
| **✅ Done — Mild** | `message_id` captured at send time; Mailgun deep-link in Show view | — |
| **✅ Done — Medium** | `delivery_status` polling via Celery; `DeliveryStatusChip` in React-Admin | Mild |
| **Phase 3** | Webhook ingestion → `CommunicationEvent`; `DeliveryEventTimeline` in admin | Medium + Mailgun webhook configured |
| **Phase 4** | `ParticipantReachabilityScore`; `ReachabilityDashboard` in React-Admin | Phase 3 |
| **Phase 5** | `CommunicationMessage` snapshot; participant inbox (`/inbox`) | Phase 3 |
| **Phase 6** | Escalation logic; two-way thread support | Phase 4 + Phase 5 |

---

## Open Questions Before Building

1. **Email open/click tracking** — requires a Mailgun tracking pixel in HTML emails. Has privacy implications; confirm with org before enabling.
2. **Escalation destination** — when a bounce escalates, should it create a staff notification inside the app, send a Slack message, or simply set a flag for the dashboard?
3. **Participant inbox permissions** — participants currently only interact with the participant frontend (not React-Admin). Confirm whether `/api/messages/` should be participant-auth or staff-only initially.
4. **`CommunicationMessage` body storage** — storing full HTML for every email will grow the DB. Consider a 90-day TTL or S3 offload for bodies older than N days.
5. **Celery Beat worker on Render** — Phase 3 still uses the polling task from Medium. Confirm the Beat worker is provisioned in `render.yaml` before deploying.
