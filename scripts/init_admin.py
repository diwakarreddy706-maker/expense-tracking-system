"""
Idempotent superuser/owner initialization script for headless cloud environments.
Reads ADMIN_USERNAME, ADMIN_PASSWORD, and ADMIN_EMAIL from environment variables.
"""
import os
import sys
from pathlib import Path

# Ensure project root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'expense_tracking_core.settings.production')
django.setup()

from django.contrib.auth import get_user_model
from apps.accounts.models import UserProfile

User = get_user_model()


def init_admin():
    username = os.getenv('ADMIN_USERNAME', 'admin').strip()
    email = os.getenv('ADMIN_EMAIL', 'admin@example.com').strip()
    password = os.getenv('ADMIN_PASSWORD', '').strip()

    if not password:
        print("ADMIN_PASSWORD environment variable not set. Skipping automatic admin initialization.")
        return

    user, created = User.objects.get_or_create(
        username=username,
        defaults={
            'email': email,
            'is_staff': True,
            'is_superuser': True,
        }
    )

    user.set_password(password)
    user.email = email
    user.is_staff = True
    user.is_superuser = True
    user.save()

    profile, _ = UserProfile.objects.get_or_create(user=user)
    profile.role = UserProfile.ROLE_OWNER
    profile.save()

    status = "Created" if created else "Updated"
    print(f"{status} superuser '{username}' with OWNER role successfully.")


if __name__ == '__main__':
    try:
        init_admin()
    except Exception as e:
        print(f"Admin initialization warning: {e}")
