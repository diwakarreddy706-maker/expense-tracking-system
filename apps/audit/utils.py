import logging
from .models import AuditLog

financial_logger = logging.getLogger('expense_tracking.financial')
security_logger = logging.getLogger('expense_tracking.security')


def get_client_ip(request):
    """Extracts client IP address from HTTP request."""
    if not request:
        return None
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


def log_audit_event(user, action, entity_type, entity_id=None, changes=None, request=None):
    """
    Persists an audit event to the database and dispatches to system logger.
    """
    ip = get_client_ip(request) if request else None
    
    # Save to database
    audit_entry = AuditLog.objects.create(
        user=user if user and user.is_authenticated else None,
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id) if entity_id is not None else None,
        changes_json=changes,
        ip_address=ip,
    )

    # Dispatch to appropriate python logger
    username = user.username if user and user.is_authenticated else 'Anonymous'
    log_msg = f"Audit: {username} performed {action} on {entity_type} (ID: {entity_id}) from {ip}"
    
    if action in [AuditLog.ACTION_LOGIN, AuditLog.ACTION_LOGOUT]:
        security_logger.info(log_msg)
    else:
        financial_logger.info(log_msg)

    return audit_entry
