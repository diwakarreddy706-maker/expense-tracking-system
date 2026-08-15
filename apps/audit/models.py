from django.db import models
from django.contrib.auth.models import User


class AuditLog(models.Model):
    """
    Immutable audit trail for tracking critical security, authentication,
    and financial actions. Defined in DATABASE_SCHEMA.md.
    """
    ACTION_CREATE = 'CREATE'
    ACTION_UPDATE = 'UPDATE'
    ACTION_SOFT_DELETE = 'SOFT_DELETE'
    ACTION_RESTORE = 'RESTORE'
    ACTION_LOGIN = 'LOGIN'
    ACTION_LOGOUT = 'LOGOUT'
    ACTION_EXPORT = 'EXPORT'
    ACTION_TRANSFER = 'TRANSFER'
    ACTION_PAYMENT = 'PAYMENT'
    ACTION_REVERSAL = 'REVERSAL'
    ACTION_DAILY_CLOSE = 'DAILY_CLOSE'

    ACTION_CHOICES = [
        (ACTION_CREATE, 'Create'),
        (ACTION_UPDATE, 'Update'),
        (ACTION_SOFT_DELETE, 'Soft Delete'),
        (ACTION_RESTORE, 'Restore'),
        (ACTION_LOGIN, 'Login'),
        (ACTION_LOGOUT, 'Logout'),
        (ACTION_EXPORT, 'Export'),
        (ACTION_TRANSFER, 'Transfer'),
        (ACTION_PAYMENT, 'Payment'),
        (ACTION_REVERSAL, 'Reversal'),
        (ACTION_DAILY_CLOSE, 'Daily Close'),
    ]

    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='audit_logs')
    action = models.CharField(max_length=20, choices=ACTION_CHOICES, db_index=True)
    entity_type = models.CharField(max_length=50, db_index=True)
    entity_id = models.CharField(max_length=50, blank=True, null=True, db_index=True)
    changes_json = models.JSONField(null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = 'audit_logs'
        verbose_name = 'Audit Log'
        verbose_name_plural = 'Audit Logs'
        ordering = ['-timestamp']

    def __str__(self):
        username = self.user.username if self.user else 'Anonymous/System'
        return f"[{self.timestamp.strftime('%Y-%m-%d %H:%M:%S')}] {username} - {self.action} on {self.entity_type} #{self.entity_id}"
