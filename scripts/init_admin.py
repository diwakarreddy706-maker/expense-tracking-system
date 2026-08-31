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


def seed_master_defaults():
    """Seeds baseline machinery types and expense categories if empty."""
    from apps.machines.models import MachineType
    from apps.expenses.models import ExpenseCategory

    # 1. Machine Types
    default_machine_types = [
        ('Tractor', 'TRACTOR'),
        ('Combine Harvester', 'COMBINE_HARVESTER'),
        ('Power Tiller', 'POWER_TILLER'),
        ('Earth Mover / JCB', 'EARTH_MOVER'),
        ('Rotavator / Cultivator', 'ROTAVATOR'),
        ('Sprayer / Drone', 'SPRAYER'),
        ('Thresher / Sheller', 'THRESHER'),
        ('Laser Land Leveler', 'LASER_LEVELER'),
        ('Baler', 'BALER'),
        ('Support Vehicle / Trailer', 'TRAILER'),
        ('Other Equipment', 'OTHER'),
    ]
    created_types = 0
    for name, code in default_machine_types:
        _, c = MachineType.objects.get_or_create(code=code, defaults={'name': name})
        if c:
            created_types += 1
    if created_types:
        print(f"Seeded {created_types} standard MachineType records.")

    # 2. Expense Categories
    default_categories = [
        ('Fuel & Lubricants', 'CAT-FUEL', '#F59E0B', 'bi-fuel-pump'),
        ('Machine Maintenance & Repairs', 'CAT-MAINT', '#EF4444', 'bi-tools'),
        ('Spare Parts', 'CAT-SPARES', '#3B82F6', 'bi-gear-wide-connected'),
        ('Employee Wages & Labor', 'CAT-WAGES', '#8B5CF6', 'bi-people'),
        ('Workshop Supplies', 'CAT-SUPPLIES', '#10B981', 'bi-box-seam'),
        ('Electricity & Utilities', 'CAT-UTILITIES', '#EC4899', 'bi-lightning-charge'),
        ('Rent & Lease', 'CAT-RENT', '#6366F1', 'bi-building'),
        ('Taxes & Insurance', 'CAT-TAXES', '#14B8A6', 'bi-file-earmark-text'),
        ('Transport & Freight', 'CAT-TRANSPORT', '#F97316', 'bi-truck'),
        ('General Overhead', 'CAT-OVERHEAD', '#64748B', 'bi-briefcase'),
    ]
    created_cats = 0
    for name, code, color, icon in default_categories:
        _, c = ExpenseCategory.objects.get_or_create(
            code=code,
            defaults={'name': name, 'color_hex': color, 'icon': icon, 'is_active': True}
        )
        if c:
            created_cats += 1
    if created_cats:
        print(f"Seeded {created_cats} default ExpenseCategory records.")


if __name__ == '__main__':
    try:
        init_admin()
        seed_master_defaults()
    except Exception as e:
        print(f"Admin initialization / seeding warning: {e}")
