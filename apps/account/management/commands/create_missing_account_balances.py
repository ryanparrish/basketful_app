"""
Management command to create AccountBalance for participants that don't have one.

This is needed for test data that was created before the signal automation was in place.
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from apps.account.models import Participant, AccountBalance


class Command(BaseCommand):
    help = 'Create AccountBalance for participants that are missing one'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be created without actually creating anything',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']

        # Find participants without account balances
        participants_without_balance = Participant.objects.filter(
            accountbalance__isnull=True,
            active=True
        )

        count = participants_without_balance.count()

        if count == 0:
            self.stdout.write(
                self.style.SUCCESS('✓ All active participants already have account balances!')
            )
            return

        self.stdout.write(f'Found {count} participant(s) without account balances:')
        
        for participant in participants_without_balance:
            self.stdout.write(
                f'  - {participant.name} (ID: {participant.id}, Customer #: {participant.customer_number})'
            )

        if dry_run:
            self.stdout.write(
                self.style.WARNING('\n--dry-run mode: No changes made')
            )
            return

        # Create account balances
        self.stdout.write('\nCreating account balances...')
        
        with transaction.atomic():
            created_count = 0
            for participant in participants_without_balance:
                # Calculate base balance based on household size
                adults = getattr(participant, 'adults', 0) or 0
                children = getattr(participant, 'children', 0) or 0
                
                base_balance = (adults * 100) + (children * 50)  # Example calculation
                
                AccountBalance.objects.create(
                    participant=participant,
                    base_balance=base_balance,
                    available_balance=0,  # Will be calculated by balance utils
                    hygiene_balance=0,
                )
                created_count += 1
                self.stdout.write(
                    self.style.SUCCESS(
                        f'  ✓ Created AccountBalance for {participant.name} '
                        f'(base: ${base_balance})'
                    )
                )

        self.stdout.write(
            self.style.SUCCESS(f'\n✓ Successfully created {created_count} account balance(s)!')
        )
