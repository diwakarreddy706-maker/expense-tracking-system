from django.contrib.admin.models import LogEntry
from django.contrib.auth import get_user_model
from django.contrib.sessions.models import Session
from django.db import transaction

from apps.audit.models import AuditLog
from apps.budgets.models import Budget, BudgetItem
from apps.employees.models import Employee, EmployeeCompensation, EmployeePayment
from apps.expenses.models import Expense
from apps.finance.models import (
    Account,
    AccountTransaction,
    Customer,
    CustomerPayment,
    DailyClosing,
    Payable,
    Receivable,
    Supplier,
    SupplierPayment,
)
from apps.fuel.models import FuelEntry
from apps.machines.models import (
    HarvesterCompliance,
    Machine,
    MachineBooking,
    MachineMaintenanceSchedule,
    MachineWorkEntry,
    MaintenanceJob,
    MaintenancePartUsage,
    RentedHarvesterOwner,
    RentedHarvesterSettlement,
)
from apps.reports.models import ReportAuditLog

User = get_user_model()


def execute_business_data_cleanup(keep_user, preserve_session_key: str | None = None) -> dict[str, int]:
    """
    Deletes operational, financial, machinery, audit, other sessions, and extra
    user records in FK-safe order while keeping `keep_user` (username and
    password hash) completely untouched.
    """
    deletion_plan = [
        ('RentedHarvesterSettlement', RentedHarvesterSettlement),
        ('MaintenancePartUsage', MaintenancePartUsage),
        ('MaintenanceJob', MaintenanceJob),
        ('MachineMaintenanceSchedule', MachineMaintenanceSchedule),
        ('HarvesterCompliance', HarvesterCompliance),
        ('FuelEntry', FuelEntry),
        ('MachineWorkEntry', MachineWorkEntry),
        ('MachineBooking', MachineBooking),
        ('CustomerPayment', CustomerPayment),
        ('SupplierPayment', SupplierPayment),
        ('EmployeePayment', EmployeePayment),
        ('EmployeeCompensation', EmployeeCompensation),
        ('Receivable', Receivable),
        ('Payable', Payable),
        ('DailyClosing', DailyClosing),
        ('AccountTransaction', AccountTransaction),
        ('BudgetItem', BudgetItem),
        ('Budget', Budget),
        ('Expense', Expense),
        ('Machine', Machine),
        ('RentedHarvesterOwner', RentedHarvesterOwner),
        ('Employee', Employee),
        ('Customer', Customer),
        ('Supplier', Supplier),
        ('Account', Account),
        ('ReportAuditLog', ReportAuditLog),
        ('AuditLog', AuditLog),
        ('AdminLogEntry', LogEntry),
    ]

    summary: dict[str, int] = {}

    with transaction.atomic():
        for label, model in deletion_plan:
            count = model.objects.count()
            if count:
                model.objects.all().delete()
            summary[label] = count

        sessions_qs = Session.objects.all()
        if preserve_session_key:
            sessions_qs = sessions_qs.exclude(session_key=preserve_session_key)
        sess_count = sessions_qs.count()
        if sess_count:
            sessions_qs.delete()
        summary['Session'] = sess_count

        extra_users = User.objects.exclude(id=keep_user.id)
        extra_count = extra_users.count()
        if extra_count:
            extra_users.delete()
        summary['ExtraUsers'] = extra_count

    return summary

