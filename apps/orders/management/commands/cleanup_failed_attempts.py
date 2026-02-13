"""
Management command to cleanup old failed order attempts (90+ days).
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from apps.orders.models import FailedOrderAttempt


class Command(BaseCommand):
    help = 'Delete failed order attempts older than specified days (default: 90)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=90,
            help='Delete records older than this many days (default: 90)',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be deleted without actually deleting',
        )

    def handle(self, *args, **options):
        days = options['days']
        dry_run = options['dry_run']
        
        cutoff_date = timezone.now() - timedelta(days=days)
        
        # Find records to delete
        old_attempts = FailedOrderAttempt.objects.filter(
            created_at__lt=cutoff_date
        )
        
        count = old_attempts.count()
        
        if count == 0:
            self.stdout.write(
                self.style.SUCCESS(
                    f'No failed order attempts older than {days} days found.'
                )
            )
            return
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f'[DRY RUN] Would delete {count} failed order attempts '
                    f'older than {days} days (before {cutoff_date.date()})'
                )
            )
            
            # Show sample of what would be deleted
            sample = old_attempts.order_by('created_at')[:5]
            self.stdout.write('\nSample records:')
            for attempt in sample:
                self.stdout.write(
                    f'  - {attempt.created_at.date()} | '
                    f'{attempt.participant.name if attempt.participant else "Unknown"} | '
                    f'{attempt.error_summary[:50]}...'
                )
            
            if count > 5:
                self.stdout.write(f'  ... and {count - 5} more')
        else:
            # Actually delete
            deleted_count, _ = old_attempts.delete()
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'Successfully deleted {deleted_count} failed order attempts '
                    f'older than {days} days.'
                )
            )
