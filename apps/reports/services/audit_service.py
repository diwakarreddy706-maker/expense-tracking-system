from datetime import date
from typing import Optional, Dict, Any
from django.utils import timezone
from apps.reports.models import ReportAuditLog


class ReportAuditService:
    """
    Records read-only governance logs whenever financial PDF reports are generated.
    """
    TYPE_FARMER_STATEMENT = ReportAuditLog.TYPE_FARMER_STATEMENT
    TYPE_PAYMENT_RECEIPT = ReportAuditLog.TYPE_PAYMENT_RECEIPT
    TYPE_WORK_INVOICE = ReportAuditLog.TYPE_WORK_INVOICE
    TYPE_MACHINERY_PNL = ReportAuditLog.TYPE_MACHINERY_PNL
    TYPE_EXPENSE_ANALYSIS = ReportAuditLog.TYPE_EXPENSE_ANALYSIS
    TYPE_RECEIVABLES_AGING = ReportAuditLog.TYPE_RECEIVABLES_AGING


    @classmethod
    def log_report_generation(
        cls,
        report_type: str,
        user=None,
        related_object_id: Optional[int] = None,
        period_start: Optional[date] = None,
        period_end: Optional[date] = None,
        as_of_date: Optional[date] = None,
        file_name: str = '',
        success: bool = True,
        metadata: Optional[Dict[str, Any]] = None
    ) -> ReportAuditLog:
        """Creates a non-financial report generation audit entry."""
        return ReportAuditLog.objects.create(
            report_type=report_type,
            user=user if (user and user.is_authenticated) else None,
            related_object_id=related_object_id,
            report_period_start=period_start,
            report_period_end=period_end,
            as_of_date=as_of_date or timezone.now().date(),
            file_name=file_name,
            success=success,
            metadata_json=metadata or {}
        )
