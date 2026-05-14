"""Periodic tasks for order-window notifications."""
import logging
from datetime import timedelta

from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task
def notify_participants_order_window_opened():
    """Check every program and email participants whose window just opened.

    Designed to run every 10 minutes via Celery beat.  For each active
    program with an enabled order window, this task:

    1. Computes the current window cycle via ``generate_window_cycles``.
    2. Determines whether the window opened within the last 30 minutes.
    3. Skips any participant whose User already has an ``order_window_opened``
       EmailLog entry dated *after* this cycle's ``opens_at``, preventing
       duplicate emails across beat ticks or retries.
    4. Dispatches ``send_order_window_opened_notification`` for every
       remaining eligible participant.
    """
    from apps.lifeskills.models import Program, ProgramPause
    from apps.account.tasks.email import send_order_window_opened_notification
    from apps.log.models import EmailLog
    from core.utils import generate_window_cycles, get_effective_config

    now = timezone.now()
    # Accept windows that opened up to 30 minutes ago.  Widened from 10 min
    # so a delayed beat (Redis blip, rolling deploy) doesn't silently skip
    # an entire cohort.  Idempotency is guaranteed by the per-cycle EmailLog
    # dedup check below — extra ticks never double-send.
    lookback = now - timedelta(minutes=30)

    # ProgramPause is global — if any pause is active, no program should fire
    # order-window emails (the pause week is a no-order week for all programs).
    pause_active = ProgramPause.objects.filter(
        pause_start__lte=now,
        pause_end__gte=now,
        archived=False,
    ).exists()

    if pause_active:
        logger.info(
            "[OrderWindow] Skipping all programs — global program pause is active"
        )
        return

    programs = Program.objects.prefetch_related('participant_set__user').all()

    for program in programs:
        try:
            config = get_effective_config(program)

            if not config['enabled']:
                continue

            cycles = generate_window_cycles(program, config, n=1)
            if not cycles:
                continue

            cycle = cycles[0]
            opens_at = cycle['opens_at']
            closes_at = cycle['closes_at']

            # Window must currently be open and have opened within the last 30 min.
            window_just_opened = lookback <= opens_at <= now
            window_currently_open = opens_at <= now < closes_at

            if not (window_just_opened and window_currently_open):
                continue

            # %-d / %-I suppress zero-padding but are Linux-only.  Build the
            # human-readable string from components so it works on macOS too.
            closes_at_local = timezone.localtime(closes_at)
            closes_at_str = (
                f"{closes_at_local.strftime('%A, %B')} "
                f"{closes_at_local.day} at "
                f"{closes_at_local.hour % 12 or 12}:{closes_at_local.strftime('%M %p')}"
            )

            # Collect user IDs that already received a notification for this cycle.
            already_notified = set(
                EmailLog.objects.filter(
                    email_type__name='order_window_opened',
                    sent_at__gte=opens_at,
                ).values_list('user_id', flat=True)
            )

            participants = (
                program.participant_set
                .filter(active=True, user__isnull=False)
                .select_related('user')
            )

            dispatched = 0
            for participant in participants:
                user = participant.user
                if user.id in already_notified:
                    continue
                send_order_window_opened_notification.delay(
                    user_id=user.id,
                    program_name=program.name,
                    closes_at_str=closes_at_str,
                )
                dispatched += 1

            if dispatched:
                logger.info(
                    "[OrderWindow] Program '%s' window opened — dispatched %d notification(s)",
                    program.name,
                    dispatched,
                )
        except Exception:
            logger.exception(
                "[OrderWindow] Error processing program '%s' — skipping",
                getattr(program, 'name', program.pk),
            )
