"""
Management command to create linked User accounts for participants missing one.

Root cause this addresses: participant-facing notifications (e.g. the
order-window-opened email) only reach participants with a linked User,
because the email pipeline (EmailLog, build_email_context) is built around
User, not Participant. Historically `create_user` defaulted to False, so
most participants created before that default changed have no User and
silently never receive these notifications.

Usage:
    python manage.py backfill_participant_user_accounts --dry-run
    python manage.py backfill_participant_user_accounts            # sends onboarding email
    python manage.py backfill_participant_user_accounts --silent   # no onboarding email
"""
from django.core.management.base import BaseCommand

from apps.account.models import Participant
from apps.account.utils.user_utils import ensure_participant_user


class Command(BaseCommand):
    help = "Create linked User accounts for active participants that don't have one."

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be created without actually creating anything',
        )
        parser.add_argument(
            '--silent',
            action='store_true',
            help='Do not queue the onboarding email for newly created users',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        send_email = not options['silent']

        candidates = Participant.objects.filter(
            active=True, user__isnull=True
        ).order_by('name')
        total = candidates.count()

        if total == 0:
            self.stdout.write(self.style.SUCCESS('All active participants already have a linked user.'))
            return

        self.stdout.write(f'Found {total} active participant(s) without a linked user:')
        for p in candidates:
            email_note = p.email or self.style.ERROR('NO EMAIL — will be skipped')
            self.stdout.write(f'  - {p.name} (ID={p.id}, {p.customer_number}) email={email_note}')

        if dry_run:
            self.stdout.write(self.style.WARNING('\n--dry-run: no changes made'))
            return

        created, skipped_no_email = 0, 0
        for p in candidates:
            success, reason = ensure_participant_user(p, send_email=send_email)
            if success:
                created += 1
            elif reason == 'no_email':
                skipped_no_email += 1

        self.stdout.write(self.style.SUCCESS(f'\nCreated {created} user account(s).'))
        if send_email and created:
            self.stdout.write('Onboarding email queued for each.')
        if skipped_no_email:
            self.stdout.write(self.style.WARNING(f'Skipped {skipped_no_email} (no email on file).'))
