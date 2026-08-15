"""
Authoritative Expense Service Layer.
Enforces Rule 1 (Decimal precision), Rule 10 (Single Authoritative Source),
atomic ledger integration, concurrent write safety, and full validation.
"""

from decimal import Decimal
from typing import Optional, Tuple, Dict, Any
from django.db import transaction
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.contrib.auth.models import User

from apps.expenses.models import Expense, ExpenseCategory
from apps.finance.models import Account, AccountTransaction, Supplier
from apps.machines.models import Machine
from apps.employees.models import Employee
from apps.finance.services.balance_service import FinancialCalculationService
from apps.audit.utils import log_audit_event
from apps.audit.models import AuditLog


class ExpenseService:
    """
    Central service for creating, reversing, and managing business expenses
    and their atomic ledger transactions.
    """

    @classmethod
    def generate_expense_code(cls, date_val=None) -> str:
        """Generates unique sequential expense code e.g. EXP-20260815-0001."""
        target_date = date_val or timezone.now().date()
        date_str = target_date.strftime('%Y%m%d')
        prefix = f"EXP-{date_str}-"
        
        # Determine sequence for date
        last_exp = Expense.objects.filter(expense_code__startswith=prefix).order_by('-id').first()
        if last_exp:
            try:
                seq = int(last_exp.expense_code.split('-')[-1]) + 1
            except (ValueError, IndexError):
                seq = 1
        else:
            seq = 1
        return f"{prefix}{seq:04d}"

    @classmethod
    def create_expense(
        cls,
        user: User,
        amount: Decimal,
        category: ExpenseCategory,
        account: Optional[Account] = None,
        payment_method: str = Expense.METHOD_CASH,
        business_segment: str = Expense.SEGMENT_GENERAL,
        expense_date = None,
        machine: Optional[Machine] = None,
        employee: Optional[Employee] = None,
        supplier: Optional[Supplier] = None,
        reference_no: Optional[str] = None,
        description: Optional[str] = None,
        is_quick_expense: bool = False,
        request = None
    ) -> Tuple[Expense, Optional[AccountTransaction]]:
        """
        Atomically creates an Expense and its single corresponding EXPENSE ledger transaction.
        Recalculates derived account balance and logs an audit entry.
        """
        # 1. Decimal & Amount Validation
        if not isinstance(amount, Decimal):
            try:
                amount = Decimal(str(amount))
            except Exception:
                raise ValidationError({"amount": "Invalid monetary amount."})

        amount = amount.quantize(Decimal('0.01'))
        if amount <= Decimal('0.00'):
            raise ValidationError({"amount": "Expense amount must be strictly greater than 0.00."})

        # 2. Category Validation
        if not category or category.is_deleted or not category.is_active:
            raise ValidationError({"category": "Expense category must be active and valid."})

        # 3. Payment Method & Account Validation
        if payment_method not in dict(Expense.PAYMENT_METHOD_CHOICES):
            raise ValidationError({"payment_method": "Invalid payment method."})

        if payment_method != Expense.METHOD_CREDIT:
            if not account or account.is_deleted or not account.is_active:
                raise ValidationError({"account": "A valid and active business account is required for non-credit expenses."})
        else:
            # Credit expenses do not immediately deduct from accounts
            account = None

        # 4. Machine Validation (if provided)
        if machine:
            if machine.is_deleted or machine.status == Machine.STATUS_DECOMMISSIONED:
                raise ValidationError({"machine": "Associated machine is decommissioned or inactive."})

        # 5. Employee Validation (if provided)
        if employee:
            if employee.is_deleted or employee.status != Employee.STATUS_ACTIVE:
                raise ValidationError({"employee": "Associated employee is inactive or deleted."})

        # 6. Supplier Validation (if provided)
        if supplier:
            if supplier.is_deleted or supplier.status != Supplier.STATUS_ACTIVE:
                raise ValidationError({"supplier": "Associated supplier is inactive or deleted."})

        expense_date = expense_date or timezone.now().date()

        # 7. Atomic Execution
        with transaction.atomic():
            # Lock account for update if immediate payment
            locked_account = None
            if account:
                locked_account = Account.objects.select_for_update().get(id=account.id)

            expense_code = cls.generate_expense_code(expense_date)

            expense = Expense.objects.create(
                expense_code=expense_code,
                expense_date=expense_date,
                amount=amount,
                category=category,
                payment_method=payment_method,
                account=locked_account,
                business_segment=business_segment,
                machine=machine,
                employee=employee,
                supplier=supplier,
                reference_no=reference_no,
                description=description,
                is_quick_expense=is_quick_expense,
                created_by=user
            )

            ledger_tx = None
            if locked_account:
                # Create authoritative EXPENSE transaction in central ledger
                ledger_tx = AccountTransaction.objects.create(
                    account=locked_account,
                    transaction_date=expense_date,
                    transaction_type=AccountTransaction.TYPE_EXPENSE,
                    direction=AccountTransaction.DIRECTION_DEBIT,
                    amount=amount,
                    reference_type='Expense',
                    reference_id=expense.id,
                    description=f"Expense {expense.expense_code}: {category.name} ({description or ''})",
                    created_by=user
                )

                # Authoritative balance update
                FinancialCalculationService.recalculate_account_balance(locked_account.id)

            # Audit Trail
            log_audit_event(
                user,
                AuditLog.ACTION_CREATE,
                'Expense',
                expense.id,
                changes={
                    'expense_code': expense.expense_code,
                    'amount': str(expense.amount),
                    'category': category.name,
                    'payment_method': payment_method,
                    'account': locked_account.account_name if locked_account else None,
                    'is_quick': is_quick_expense
                },
                request=request
            )

            # 8. Credit Expense Integration: Create Supplier Payable if supplier is provided
            if payment_method == Expense.METHOD_CREDIT and supplier:
                from apps.finance.services.settlement_service import SupplierPayableService
                SupplierPayableService.create_payable(
                    user=user,
                    supplier=supplier,
                    total_amount=amount,
                    bill_date=expense_date,
                    bill_no=reference_no,
                    linked_expense=expense,
                    notes=f"Credit Expense {expense.expense_code}: {description or ''}",
                    request=request
                )

            return expense, ledger_tx

    @classmethod
    def reverse_expense(
        cls,
        expense_id: int,
        user: User,
        reason: str,
        request = None
    ) -> Tuple[Expense, Optional[AccountTransaction]]:
        """
        Reverses a posted financial expense by recording an authoritative REVERSAL credit transaction.
        Enforces Rule 10: History is preserved; never mutates original posted records to zero.
        """
        if not user.profile.is_owner and not user.is_superuser:
            raise ValidationError("Financial reversals are strictly restricted to system Owners.")

        if not reason or len(reason.strip()) < 5:
            raise ValidationError({"reason": "A valid explanation (minimum 5 characters) is required for financial reversals."})

        with transaction.atomic():
            expense = Expense.objects.select_for_update().get(id=expense_id, is_deleted=False)

            if expense.is_reversed:
                raise ValidationError("This expense has already been reversed.")

            expense.is_reversed = True
            expense.save(update_fields=['is_reversed', 'updated_at'])

            reversal_tx = None
            if expense.account:
                locked_account = Account.objects.select_for_update().get(id=expense.account.id)

                # Create REVERSAL transaction in central ledger (Credit back to account)
                reversal_tx = AccountTransaction.objects.create(
                    account=locked_account,
                    transaction_date=timezone.now().date(),
                    transaction_type=AccountTransaction.TYPE_REVERSAL,
                    direction=AccountTransaction.DIRECTION_CREDIT,
                    amount=expense.amount,
                    reference_type='Expense',
                    reference_id=expense.id,
                    description=f"Reversal of {expense.expense_code}: {reason.strip()}",
                    created_by=user
                )

                # Authoritative balance update
                FinancialCalculationService.recalculate_account_balance(locked_account.id)

            # Audit Trail
            log_audit_event(
                user,
                AuditLog.ACTION_REVERSAL,
                'Expense',
                expense.id,
                changes={'expense_code': expense.expense_code, 'reason': reason.strip(), 'amount': str(expense.amount)},
                request=request
            )

            return expense, reversal_tx

    @classmethod
    def soft_delete_expense(cls, expense_id: int, user: User, request=None) -> Expense:
        """
        Soft deletes an unreversed expense and voids associated ledger transactions.
        """
        if not user.profile.is_owner and not user.is_superuser:
            raise ValidationError("Deleting expense records is restricted to system Owners.")

        with transaction.atomic():
            expense = Expense.objects.select_for_update().get(id=expense_id, is_deleted=False)
            expense.is_deleted = True
            expense.save(update_fields=['is_deleted', 'updated_at'])

            if expense.account:
                locked_account = Account.objects.select_for_update().get(id=expense.account.id)
                # Soft delete corresponding ledger transaction
                AccountTransaction.objects.filter(
                    reference_type='Expense',
                    reference_id=expense.id
                ).update(is_deleted=True)

                FinancialCalculationService.recalculate_account_balance(locked_account.id)

            log_audit_event(
                user,
                AuditLog.ACTION_SOFT_DELETE,
                'Expense',
                expense.id,
                changes={'expense_code': expense.expense_code},
                request=request
            )

            return expense
