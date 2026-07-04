"""
Read-only diagnostic for the order-window-opened email notification pipeline.

Checks every layer independently so a report can distinguish between:
  - the Celery Beat schedule never firing the task at all
  - the task firing but finding no eligible programs/participants
  - the task dispatching but the EmailType being missing/inactive
  - Django successfully handing off to Mailgun but Mailgun failing delivery

Usage:
    python manage.py diagnose_order_window_emails
"""
from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta


class Command(BaseCommand):
    help = "Report the health of every layer in the order-window-opened email pipeline."

    def handle(self, *args, **options):
        self.stdout.write(self.style.MIGRATE_HEADING("\n1. Email backend"))
        self.stdout.write(f"  EMAIL_BACKEND     : {settings.EMAIL_BACKEND}")
        if 'mailgun' in settings.EMAIL_BACKEND.lower():
            anymail = getattr(settings, 'ANYMAIL', {})
            api_key = anymail.get('MAILGUN_API_KEY')
            self.stdout.write(
                f"  MAILGUN_API_KEY   : {'set (' + str(len(api_key)) + ' chars)' if api_key else self.style.ERROR('MISSING')}"
            )
            self.stdout.write(f"  MAILGUN_SENDER_DOMAIN : {anymail.get('MAILGUN_SENDER_DOMAIN')}")
        else:
            self.stdout.write(
                self.style.WARNING("  Using console backend — no real emails will be delivered.")
            )

        self.stdout.write(self.style.MIGRATE_HEADING("\n2. Celery Beat schedule (DB rows)"))
        try:
            from django_celery_beat.models import PeriodicTask
            expected = [
                'create_weekly_combined_orders',
                'cleanup-expired-pause-flags',
                'sync-mailgun-delivery-status',
                'notify-order-window-opened',
                'retry-failed-emails',
            ]
            for name in expected:
                pt = PeriodicTask.objects.filter(name=name).first()
                if pt is None:
                    self.stdout.write(
                        self.style.ERROR(f"  {name:35s} NOT IN DB — beat has never synced this entry")
                    )
                    continue
                schedule = pt.crontab or pt.interval or pt.schedule
                status = self.style.SUCCESS("enabled") if pt.enabled else self.style.ERROR("DISABLED")
                self.stdout.write(
                    f"  {name:35s} {status:20s} schedule={schedule} "
                    f"last_run_at={pt.last_run_at} total_run_count={pt.total_run_count}"
                )
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"  Could not query PeriodicTask: {e}"))

        self.stdout.write(self.style.MIGRATE_HEADING("\n3. EmailType configuration"))
        from apps.log.models import EmailType
        et = EmailType.objects.filter(name='order_window_opened').first()
        if et is None:
            self.stdout.write(self.style.ERROR("  'order_window_opened' EmailType MISSING from DB"))
        else:
            self.stdout.write(
                f"  is_active={et.is_active}  subject={et.subject!r}"
            )

        self.stdout.write(self.style.MIGRATE_HEADING("\n4. Global OrderWindowSettings"))
        from core.models import OrderWindowSettings
        gs = OrderWindowSettings.get_settings()
        self.stdout.write(
            f"  enabled={gs.enabled}  hours_before_class={gs.hours_before_class}  "
            f"hours_before_close={gs.hours_before_close}"
        )

        self.stdout.write(self.style.MIGRATE_HEADING("\n5. Per-program eligibility"))
        from apps.lifeskills.models import Program
        from core.utils import get_effective_config
        for program in Program.objects.all():
            config = get_effective_config(program)
            eligible = (
                program.participant_set
                .filter(active=True, user__isnull=False)
                .exclude(user__email='')
                .count()
            )
            total = program.participant_set.filter(active=True).count()
            flag = "" if config['enabled'] else self.style.ERROR("  <-- order window DISABLED")
            self.stdout.write(
                f"  {program.name:30s} enabled={config['enabled']!s:5s} "
                f"({config['enabled_source']:7s}) eligible={eligible}/{total} active participants{flag}"
            )

        self.stdout.write(self.style.MIGRATE_HEADING("\n6. Recent EmailLog activity (order_window_opened, last 30 days)"))
        from apps.log.models import EmailLog
        cutoff = timezone.now() - timedelta(days=30)
        logs = EmailLog.objects.filter(email_type__name='order_window_opened', sent_at__gte=cutoff)
        total = logs.count()
        if total == 0:
            self.stdout.write(
                self.style.ERROR(
                    "  ZERO EmailLog entries in the last 30 days — the task is not "
                    "dispatching at all (check sections 1-5 above for why)."
                )
            )
        else:
            for status in ['sent', 'failed']:
                count = logs.filter(status=status).count()
                self.stdout.write(f"  status={status:8s} count={count}")
            self.stdout.write("  delivery_status breakdown (Mailgun-reported outcome):")
            for ds in ['unknown', 'delivered', 'bounced', 'complained', 'unsubscribed', 'failed']:
                count = logs.filter(delivery_status=ds).count()
                if count:
                    self.stdout.write(f"    {ds:14s} {count}")
            self.stdout.write("\n  Most recent 5 entries:")
            for log in logs.order_by('-sent_at')[:5]:
                self.stdout.write(
                    f"    {log.sent_at}  user_id={log.user_id}  status={log.status}  "
                    f"delivery_status={log.delivery_status}  error={log.error_message[:80]}"
                )

        self.stdout.write("")
