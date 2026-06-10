"""
Management command to manually trigger final_cleanup_after_pause_end for one or
more ProgramPause records.

Typical use cases:
  - A pause ended but the Celery eta task never fired (broker outage, missed eta).
  - Staff re-saved a pause after its window closed and want to force voucher reset.
  - Verifying voucher state without committing changes (--dry-run).

Usage:
    python manage.py run_pause_cleanup <pause_id> [<pause_id> ...]
    python manage.py run_pause_cleanup 8 9 --dry-run
    python manage.py run_pause_cleanup 8 --force
"""
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from apps.lifeskills.models import ProgramPause
from apps.voucher.models import Voucher


class Command(BaseCommand):
    help = "Run final cleanup for one or more ProgramPause IDs."

    def add_arguments(self, parser):
        parser.add_argument(
            "pause_ids",
            nargs="+",
            type=int,
            metavar="PAUSE_ID",
            help="One or more ProgramPause IDs to clean up.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help=(
                "Show what would happen without writing any changes. "
                "Ignores --force."
            ),
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help=(
                "Bypass the pause_end > now guard. Use when the pause technically "
                "hasn't ended yet but you need to reset vouchers immediately."
            ),
        )

    def handle(self, *args, **options):
        pause_ids = options["pause_ids"]
        dry_run = options["dry_run"]
        force = options["force"] and not dry_run  # --force is a no-op in dry-run

        now = timezone.now()

        for pause_id in pause_ids:
            self.stdout.write(f"\nProgramPause ID={pause_id}")
            self.stdout.write("-" * 40)

            try:
                pp = ProgramPause.objects.all_pauses().get(id=pause_id)
            except ProgramPause.DoesNotExist:
                raise CommandError(f"ProgramPause ID={pause_id} not found.")

            self.stdout.write(f"  pause_start : {pp.pause_start}")
            self.stdout.write(f"  pause_end   : {pp.pause_end}")
            self.stdout.write(f"  archived    : {pp.archived}")

            # Timing guard check — mirrors the task's own guard
            if pp.pause_end and pp.pause_end > now and not force:
                self.stdout.write(
                    self.style.WARNING(
                        f"  Pause hasn't ended yet (ends {pp.pause_end}, now={now}).\n"
                        f"  Pass --force to bypass this guard."
                    )
                )
                continue

            if force and pp.pause_end and pp.pause_end > now:
                self.stdout.write(
                    self.style.WARNING("  --force: bypassing pause_end guard.")
                )

            flagged = Voucher.objects.filter(program_pause_flag=True, active=True)
            flagged_count = flagged.count()

            self.stdout.write(f"  flagged vouchers : {flagged_count}")
            if flagged_count:
                ids = list(flagged.values_list("id", flat=True))
                self.stdout.write(f"  voucher IDs      : {ids}")

            will_archive = not pp.archived

            if dry_run:
                self.stdout.write(
                    self.style.WARNING(
                        f"  [DRY RUN] Would reset {flagged_count} voucher(s) "
                        f"and {'archive' if will_archive else 'skip archive of'} "
                        f"this pause."
                    )
                )
                continue

            # Live run — call the task directly (in-process, no broker needed)
            from apps.lifeskills.tasks.program_pause import final_cleanup_after_pause_end

            final_cleanup_after_pause_end(pause_id=pause_id, force=force)

            self.stdout.write(
                self.style.SUCCESS(
                    f"  Done. Reset {flagged_count} voucher(s); "
                    f"pause {'archived' if will_archive else 'was already archived'}."
                )
            )

        self.stdout.write("")
