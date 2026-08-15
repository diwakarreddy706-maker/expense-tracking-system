from django.db import models
from django.contrib.auth.models import User, Group
from django.db.models.signals import post_save
from django.dispatch import receiver


class UserProfile(models.Model):
    """
    Extends Django's native auth_user with canonical business roles
    and contact details as defined in DATABASE_SCHEMA.md.
    """
    ROLE_OWNER = 'OWNER'
    ROLE_ACCOUNTANT = 'ACCOUNTANT'
    ROLE_MANAGER = 'MANAGER'
    ROLE_EMPLOYEE = 'EMPLOYEE'

    ROLE_CHOICES = [
        (ROLE_OWNER, 'Owner'),
        (ROLE_ACCOUNTANT, 'Accountant'),
        (ROLE_MANAGER, 'Manager'),
        (ROLE_EMPLOYEE, 'Employee'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default=ROLE_EMPLOYEE,
        db_index=True,
        help_text="Canonical business role for RBAC"
    )
    phone_number = models.CharField(max_length=15, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'user_profiles'
        verbose_name = 'User Profile'
        verbose_name_plural = 'User Profiles'

    def __str__(self):
        return f"{self.user.username} ({self.get_role_display()})"

    @property
    def is_owner(self):
        return self.role == self.ROLE_OWNER

    @property
    def is_accountant(self):
        return self.role == self.ROLE_ACCOUNTANT

    @property
    def is_manager(self):
        return self.role == self.ROLE_MANAGER

    @property
    def is_employee(self):
        return self.role == self.ROLE_EMPLOYEE


@receiver(post_save, sender=User)
def create_or_update_user_profile(sender, instance, created, **kwargs):
    """
    Automatically creates/syncs UserProfile and assigns corresponding Django Group.
    """
    if created:
        # Determine default role (superuser -> OWNER, otherwise -> EMPLOYEE)
        default_role = UserProfile.ROLE_OWNER if instance.is_superuser else UserProfile.ROLE_EMPLOYEE
        profile = UserProfile.objects.create(user=instance, role=default_role)
    else:
        profile, _ = UserProfile.objects.get_or_create(user=instance)

    # Sync Django Group
    group, _ = Group.objects.get_or_create(name=profile.role)
    instance.groups.set([group])
