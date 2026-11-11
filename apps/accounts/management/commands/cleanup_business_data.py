from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from apps.accounts.cleanup_service import execute_business_data_cleanup
from apps.accounts.models import UserProfile

User = get_user_model()


class Command(BaseCommand):
    help = (
        "Deletes operational, financial, machinery, audit, session, and extra user "
        "records while preserving the primary Owner user's username and password untouched."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--keep-username',
            type=str,
            default='Doddanna Gowad',
            help="Username of the Owner account to keep untouched (default: 'Doddanna Gowad').",
        )
        parser.add_argument(
            '--yes',
            action='store_true',
            help='Confirm irreversible deletion of business data.',
        )

    def _resolve_keep_user(self, keep_username: str):
        user = User.objects.filter(username__iexact=keep_username.strip()).first()
        if user:
            return user

        owners = User.objects.filter(
            is_active=True,
            profile__role=UserProfile.ROLE_OWNER,
        ).order_by('id')
        if owners.count() == 1:
            return owners.first()

        raise CommandError(
            f"Could not uniquely locate Owner user '{keep_username}'. "
            "Aborted without deleting any data."
        )

    def handle(self, *args, **options):
        if not options['yes']:
            raise CommandError("Refusing to delete data without '--yes' flag.")

        keep_user = self._resolve_keep_user(options['keep_username'])
        summary = execute_business_data_cleanup(keep_user)

        for label, count in summary.items():
            self.stdout.write(f"Cleared {label}: {count}")

        self.stdout.write(
            self.style.SUCCESS(
                f"Data cleanup complete. Preserved account '{keep_user.username}' (username & password untouched)."
            )
        )
