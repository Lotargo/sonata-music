from django.core.management.base import BaseCommand
from music.models import Track


class Command(BaseCommand):
    help = "Reconciles database records with physical media on disk, clearing dead covers and optionally pruning orphaned tracks."

    def add_arguments(self, parser):
        parser.add_argument(
            '--prune-orphans',
            action='store_true',
            help='Delete track records whose audio files (both original and processed) no longer exist on disk.',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Report missing media without making changes to the database.',
        )

    def handle(self, *args, **options):
        dry_run = options.get('dry_run', False)
        prune_orphans = options.get('prune_orphans', False)

        tracks = list(Track.objects.all())
        dead_cover_count = 0
        orphaned_track_count = 0

        self.stdout.write(self.style.NOTICE(f"Scanning {len(tracks)} tracks for missing media on disk..."))

        for track in tracks:
            # Check dead covers
            if track.cover_image and not track.has_cover:
                dead_cover_count += 1
                self.stdout.write(
                    self.style.WARNING(
                        f"  [Missing Cover] Track #{track.id} '{track.display_title}' -> {track.cover_image.name}"
                    )
                )
                if not dry_run:
                    track.cover_image = None
                    track.save(update_fields=['cover_image'])

            # Check dead audio tracks
            if not track.is_available:
                orphaned_track_count += 1
                self.stdout.write(
                    self.style.ERROR(
                        f"  [Orphaned Track] Track #{track.id} '{track.display_title}' has no physical audio on disk."
                    )
                )
                if prune_orphans and not dry_run:
                    track.delete()
                    self.stdout.write(self.style.SUCCESS(f"    -> Deleted orphaned track #{track.id}"))

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f"\n[DRY RUN] Found {dead_cover_count} missing covers and {orphaned_track_count} orphaned tracks."
                )
            )
        else:
            status_msg = f"\n[SUCCESS] Reconciled media: {dead_cover_count} dead cover links cleared."
            if prune_orphans:
                status_msg += f" {orphaned_track_count} orphaned tracks deleted."
            elif orphaned_track_count > 0:
                status_msg += f" (Note: {orphaned_track_count} orphaned tracks remain. Re-run with --prune-orphans to delete them)."
            self.stdout.write(self.style.SUCCESS(status_msg))
