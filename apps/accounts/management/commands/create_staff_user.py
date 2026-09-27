import getpass
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from apps.accounts.models import UserProfile

User = get_user_model()


class Command(BaseCommand):
    help = 'Provision a new staff account with canonical RBAC role and credentials'

    def add_arguments(self, parser):
        parser.add_argument('--username', type=str, required=True, help='Unique username for login')
        parser.add_argument(
            '--role',
            type=str,
            default=UserProfile.ROLE_ACCOUNTANT,
            choices=[UserProfile.ROLE_OWNER, UserProfile.ROLE_ACCOUNTANT, UserProfile.ROLE_MANAGER, UserProfile.ROLE_EMPLOYEE],
            help='Canonical business role (OWNER, ACCOUNTANT, MANAGER, EMPLOYEE)'
        )
        parser.add_argument('--first-name', type=str, default='', help='First name of staff member')
        parser.add_argument('--last-name', type=str, default='', help='Last name of staff member')
        parser.add_argument('--email', type=str, default='', help='Email address')
        parser.add_argument('--phone', type=str, default='', help='10-digit mobile contact number')
        parser.add_argument('--password', type=str, default='', help='Initial password (prompted securely if omitted)')

    def handle(self, *args, **options):
        username = options['username'].strip()
        role = options['role'].strip().upper()
        first_name = options['first_name'].strip()
        last_name = options['last_name'].strip()
        email = options['email'].strip()
        phone = options['phone'].strip()
        password = options['password']

        if User.objects.filter(username__iexact=username).exists():
            raise CommandError(f"User with username '{username}' already exists.")

        while not password:
            raw_password = getpass.getpass(f"Enter password for '{username}': ")
            confirm_password = getpass.getpass("Confirm password: ")
            if raw_password != confirm_password:
                self.stderr.write(self.style.ERROR("Passwords do not match. Please try again."))
                continue
            try:
                validate_password(raw_password)
                password = raw_password
            except ValidationError as err:
                for msg in err.messages:
                    self.stderr.write(self.style.ERROR(f"Password error: {msg}"))

        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name
        )

        if role in (UserProfile.ROLE_OWNER, UserProfile.ROLE_ACCOUNTANT):
            user.is_staff = True
            user.save(update_fields=['is_staff'])

        profile, _ = UserProfile.objects.get_or_create(user=user)
        profile.role = role
        profile.phone_number = phone
        profile.save()

        self.stdout.write(self.style.SUCCESS(
            f"Successfully created staff account '{username}' with role '{profile.get_role_display()}'."
        ))
