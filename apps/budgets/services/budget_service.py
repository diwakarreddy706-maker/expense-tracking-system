"""
Authoritative Budgeting & Financial Controls Service Layer.
Enforces Rule 1 (Decimal precision), Rule 5 (separation of budget from cash balances),
Rule 8 (Credit expense counts once), Rule 9 (Reversal decreases actual), and Alert Thresholds.
"""

from decimal import Decimal
from typing import Optional, Dict, Any, List
from django.db import transaction
from django.db.models import Sum, Q
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.contrib.auth.models import User

from apps.budgets.models import Budget, BudgetItem
from apps.expenses.models import Expense, ExpenseCategory
from apps.machines.models import Machine
from apps.audit.utils import log_audit_event
from apps.audit.models import AuditLog


class BudgetService:
    """
    Service for managing operational budgets, tracking budget vs actual spending,
    and triggering financial control warnings without corrupting the financial ledger.
    """

    # Configurable control alert thresholds
    THRESHOLD_WARNING = Decimal('80.00')
    THRESHOLD_EXCEEDED = Decimal('100.00')

    STATUS_NORMAL = 'NORMAL'
    STATUS_WARNING = 'WARNING'
    STATUS_EXCEEDED = 'EXCEEDED'

    @classmethod
    def get_alert_status(cls, utilization_pct: Decimal) -> str:
        """Determines control alert state based on utilization percentage."""
        if utilization_pct >= cls.THRESHOLD_EXCEEDED:
            return cls.STATUS_EXCEEDED
        elif utilization_pct >= cls.THRESHOLD_WARNING:
            return cls.STATUS_WARNING
        return cls.STATUS_NORMAL

    @classmethod
    def calculate_budget_vs_actual(cls, budget: Budget) -> Dict[str, Any]:
        """
        Calculates item-level and aggregate budget vs actual spending for a budget.
        Uses existing authoritative expenses data without double-counting.
        """
        zero = Decimal('0.00')
        items = budget.items.select_related('category', 'machine').all()

        item_results = []
        total_allocated = zero
        total_actual = zero

        for item in items:
            # Query actual non-deleted, non-reversed expenses in period
            exp_qs = Expense.objects.filter(
                expense_date__year=budget.period_year,
                expense_date__month=budget.period_month,
                category=item.category,
                is_deleted=False,
                is_reversed=False
            )

            if item.machine:
                exp_qs = exp_qs.filter(machine=item.machine)

            actual = exp_qs.aggregate(s=Sum('amount'))['s'] or zero
            actual = actual.quantize(Decimal('0.01'))

            allocated = item.allocated_amount.quantize(Decimal('0.01'))
            remaining = (allocated - actual).quantize(Decimal('0.01'))

            if allocated > zero:
                utilization = ((actual / allocated) * Decimal('100.00')).quantize(Decimal('0.01'))
            else:
                utilization = zero

            status = cls.get_alert_status(utilization)

            item_results.append({
                'item_id': item.id,
                'category': item.category,
                'machine': item.machine,
                'allocated_amount': allocated,
                'actual_amount': actual,
                'remaining_amount': remaining,
                'utilization_pct': utilization,
                'status': status,
                'notes': item.notes,
            })

            total_allocated += allocated
            total_actual += actual

        total_remaining = (total_allocated - total_actual).quantize(Decimal('0.01'))
        if total_allocated > zero:
            overall_utilization = ((total_actual / total_allocated) * Decimal('100.00')).quantize(Decimal('0.01'))
        else:
            overall_utilization = zero

        overall_status = cls.get_alert_status(overall_utilization)

        return {
            'budget': budget,
            'items': item_results,
            'total_allocated': total_allocated,
            'total_actual': total_actual,
            'total_remaining': total_remaining,
            'overall_utilization': overall_utilization,
            'overall_status': overall_status,
        }

    @classmethod
    def create_budget(
        cls,
        user: User,
        title: str,
        period_month: int,
        period_year: int,
        business_segment: str = Budget.SEGMENT_GENERAL,
        items_data: Optional[List[Dict[str, Any]]] = None,
        notes: Optional[str] = None,
        status: str = Budget.STATUS_ACTIVE,
        request = None
    ) -> Budget:
        """
        Creates a new budget with allocations.
        Enforces unique period/segment constraint and server-side RBAC.
        """
        profile = getattr(user, 'profile', None)
        is_owner = getattr(profile, 'is_owner', False) if profile else False
        is_accountant = getattr(profile, 'is_accountant', False) if profile else False
        if not is_owner and not is_accountant and not getattr(user, 'is_superuser', False):
            raise ValidationError("Creating budgets is restricted to Owners and Accountants.")

        if not (1 <= period_month <= 12):
            raise ValidationError({"period_month": "Month must be between 1 and 12."})

        if period_year < 2000 or period_year > 2100:
            raise ValidationError({"period_year": "Invalid budget year."})

        # Overlap Protection (Section 14)
        existing = Budget.objects.filter(
            period_month=period_month,
            period_year=period_year,
            business_segment=business_segment,
            is_deleted=False
        ).exclude(status=Budget.STATUS_CANCELLED).first()

        if existing:
            raise ValidationError(
                f"A budget already exists for {period_month:02d}/{period_year} in segment '{dict(Budget.SEGMENT_CHOICES).get(business_segment)}' (ID: {existing.id})."
            )

        with transaction.atomic():
            budget = Budget.objects.create(
                title=title.strip(),
                period_month=period_month,
                period_year=period_year,
                business_segment=business_segment,
                status=status,
                notes=notes,
                created_by=user
            )

            if items_data:
                for item in items_data:
                    category = item.get('category')
                    machine = item.get('machine')
                    allocated = item.get('allocated_amount')
                    item_note = item.get('notes')

                    if not isinstance(allocated, Decimal):
                        allocated = Decimal(str(allocated))

                    if allocated <= Decimal('0.00'):
                        raise ValidationError(f"Allocated amount for {category.name} must be greater than zero.")

                    BudgetItem.objects.create(
                        budget=budget,
                        category=category,
                        machine=machine,
                        allocated_amount=allocated.quantize(Decimal('0.01')),
                        notes=item_note
                    )

            log_audit_event(
                user,
                AuditLog.ACTION_CREATE,
                'Budget',
                budget.id,
                changes={
                    'title': budget.title,
                    'period': f"{budget.period_month:02d}/{budget.period_year}",
                    'segment': budget.business_segment,
                    'total_allocated': str(budget.total_allocated_amount),
                    'status': budget.status
                },
                request=request
            )

            return budget

    @classmethod
    def update_budget(
        cls,
        budget_id: int,
        user: User,
        title: Optional[str] = None,
        status: Optional[str] = None,
        notes: Optional[str] = None,
        items_data: Optional[List[Dict[str, Any]]] = None,
        request = None
    ) -> Budget:
        """
        Updates an existing budget and logs audit trail.
        """
        profile = getattr(user, 'profile', None)
        is_owner = getattr(profile, 'is_owner', False) if profile else False
        is_accountant = getattr(profile, 'is_accountant', False) if profile else False
        if not is_owner and not is_accountant and not getattr(user, 'is_superuser', False):
            raise ValidationError("Editing budgets is restricted to Owners and Accountants.")

        budget = Budget.objects.filter(id=budget_id, is_deleted=False).first()
        if not budget:
            raise ValidationError("Budget not found.")

        with transaction.atomic():
            changes = {}
            if title and title.strip() != budget.title:
                changes['title'] = {'old': budget.title, 'new': title.strip()}
                budget.title = title.strip()

            if status and status != budget.status:
                changes['status'] = {'old': budget.status, 'new': status}
                budget.status = status

            if notes is not None and notes != budget.notes:
                budget.notes = notes

            budget.save()

            if items_data is not None:
                # Sync budget items
                budget.items.all().delete()
                for item in items_data:
                    allocated = item.get('allocated_amount')
                    if not isinstance(allocated, Decimal):
                        allocated = Decimal(str(allocated))

                    BudgetItem.objects.create(
                        budget=budget,
                        category=item.get('category'),
                        machine=item.get('machine'),
                        allocated_amount=allocated.quantize(Decimal('0.01')),
                        notes=item.get('notes')
                    )
                changes['items_updated'] = True

            action = AuditLog.ACTION_UPDATE
            if status == Budget.STATUS_CANCELLED:
                action = AuditLog.ACTION_SOFT_DELETE

            log_audit_event(
                user,
                action,
                'Budget',
                budget.id,
                changes=changes,
                request=request
            )

            return budget

    @classmethod
    def get_budget_dashboard_summary(cls, period_month: int, period_year: int) -> Dict[str, Any]:
        """
        Calculates aggregate budget summary across categories, machines, and segments for a month.
        """
        zero = Decimal('0.00')
        budgets = Budget.objects.filter(
            period_month=period_month,
            period_year=period_year,
            status=Budget.STATUS_ACTIVE,
            is_deleted=False
        ).prefetch_related('items__category', 'items__machine')

        total_budgeted = zero
        total_spent = zero
        category_breakdown = {}
        machine_breakdown = {}
        segment_breakdown = {}

        for b in budgets:
            res = cls.calculate_budget_vs_actual(b)
            total_budgeted += res['total_allocated']
            total_spent += res['total_actual']

            # Segment grouping
            seg_name = b.get_business_segment_display()
            if seg_name not in segment_breakdown:
                segment_breakdown[seg_name] = {'allocated': zero, 'actual': zero}
            segment_breakdown[seg_name]['allocated'] += res['total_allocated']
            segment_breakdown[seg_name]['actual'] += res['total_actual']

            # Items grouping
            for item in res['items']:
                cat_name = item['category'].name
                if cat_name not in category_breakdown:
                    category_breakdown[cat_name] = {'allocated': zero, 'actual': zero}
                category_breakdown[cat_name]['allocated'] += item['allocated_amount']
                category_breakdown[cat_name]['actual'] += item['actual_amount']

                if item['machine']:
                    m_name = f"{item['machine'].machine_code} - {item['machine'].name}"
                    if m_name not in machine_breakdown:
                        machine_breakdown[m_name] = {'allocated': zero, 'actual': zero}
                    machine_breakdown[m_name]['allocated'] += item['allocated_amount']
                    machine_breakdown[m_name]['actual'] += item['actual_amount']

        total_remaining = (total_budgeted - total_spent).quantize(Decimal('0.01'))
        if total_budgeted > zero:
            utilization = ((total_spent / total_budgeted) * Decimal('100.00')).quantize(Decimal('0.01'))
        else:
            utilization = zero

        return {
            'period_month': period_month,
            'period_year': period_year,
            'total_budgeted': total_budgeted.quantize(Decimal('0.01')),
            'total_spent': total_spent.quantize(Decimal('0.01')),
            'total_remaining': total_remaining,
            'overall_utilization': utilization,
            'status': cls.get_alert_status(utilization),
            'category_breakdown': category_breakdown,
            'machine_breakdown': machine_breakdown,
            'segment_breakdown': segment_breakdown,
        }
