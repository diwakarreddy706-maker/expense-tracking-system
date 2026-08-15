"""
Authoritative Fuel & Lubricant Service Layer.
Enforces Rule 1 (Decimal precision), Rule 9 (1:1 FuelEntry -> Expense linkage),
Meter rollback validation, and atomic ledger integration.
"""

from decimal import Decimal
from typing import Optional, Tuple
from django.db import transaction
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.contrib.auth.models import User

from apps.fuel.models import FuelEntry
from apps.machines.models import Machine
from apps.finance.models import Account, Supplier
from apps.employees.models import Employee
from apps.expenses.models import Expense, ExpenseCategory
from apps.expenses.services.expense_service import ExpenseService
from apps.audit.utils import log_audit_event
from apps.audit.models import AuditLog


class FuelService:
    """
    Central service for recording and managing machinery fuel/lubricant logs
    and their atomic 1:1 financial expenses and ledger entries.
    """

    @classmethod
    def generate_fuel_code(cls, date_val=None) -> str:
        """Generates unique sequential fuel code e.g. FUEL-20260815-0001."""
        target_date = date_val or timezone.now().date()
        date_str = target_date.strftime('%Y%m%d')
        prefix = f"FUEL-{date_str}-"

        last_entry = FuelEntry.objects.filter(fuel_code__startswith=prefix).order_by('-id').first()
        if last_entry:
            try:
                seq = int(last_entry.fuel_code.split('-')[-1]) + 1
            except (ValueError, IndexError):
                seq = 1
        else:
            seq = 1
        return f"{prefix}{seq:04d}"

    @classmethod
    def get_or_create_fuel_category(cls, fuel_type: str) -> ExpenseCategory:
        """Resolves or creates the appropriate category for fuel/lubricant expenses."""
        category_name = f"Fuel & Lubricants - {dict(FuelEntry.FUEL_TYPE_CHOICES).get(fuel_type, fuel_type)}"
        code_suffix = fuel_type.replace('_', '-')
        cat_code = f"CAT-FUEL-{code_suffix}"

        cat, _ = ExpenseCategory.objects.get_or_create(
            code=cat_code,
            defaults={
                'name': category_name,
                'color_hex': '#F59E0B',
                'icon_class': 'bi-fuel-pump-fill',
                'is_active': True
            }
        )
        return cat

    @classmethod
    def create_fuel_entry(
        cls,
        user: User,
        machine: Machine,
        fuel_type: str,
        quantity: Decimal,
        unit_price: Decimal,
        meter_reading: Decimal,
        payment_method: str = FuelEntry.METHOD_CASH,
        account: Optional[Account] = None,
        supplier: Optional[Supplier] = None,
        operator: Optional[Employee] = None,
        date_val = None,
        reference_no: Optional[str] = None,
        notes: Optional[str] = None,
        request = None
    ) -> FuelEntry:
        """
        Atomically records a FuelEntry and creates its 1:1 linked Expense and Ledger Transaction.
        Enforces meter integrity and server-side calculation.
        """
        # 1. Decimal & Quantity/Price Validations
        if not isinstance(quantity, Decimal):
            try:
                quantity = Decimal(str(quantity))
            except Exception:
                raise ValidationError({"quantity": "Invalid quantity."})

        if not isinstance(unit_price, Decimal):
            try:
                unit_price = Decimal(str(unit_price))
            except Exception:
                raise ValidationError({"unit_price": "Invalid unit price."})

        if not isinstance(meter_reading, Decimal):
            try:
                meter_reading = Decimal(str(meter_reading))
            except Exception:
                raise ValidationError({"meter_reading": "Invalid meter reading."})

        quantity = quantity.quantize(Decimal('0.01'))
        unit_price = unit_price.quantize(Decimal('0.01'))
        meter_reading = meter_reading.quantize(Decimal('0.01'))

        if quantity <= Decimal('0.00'):
            raise ValidationError({"quantity": "Fuel quantity must be strictly greater than zero."})

        if unit_price <= Decimal('0.00'):
            raise ValidationError({"unit_price": "Unit price must be strictly greater than zero."})

        # Authoritative server-side calculation (Rule 1 & Rule 5)
        total_amount = (quantity * unit_price).quantize(Decimal('0.01'))

        # 2. Machine Validation
        if not machine or machine.is_deleted or machine.status == Machine.STATUS_DECOMMISSIONED:
            raise ValidationError({"machine": "A valid and active machine is required for fuel logs."})

        # 3. Meter Rollback Prevention (Section 8)
        if meter_reading < machine.current_meter_reading:
            unit_label = machine.get_meter_unit_display()
            raise ValidationError({
                "meter_reading": f"Meter rollback detected! Entered {meter_reading} {unit_label} is lower than current machine reading ({machine.current_meter_reading} {unit_label})."
            })

        # 4. Supplier & Operator Validations
        if supplier and (supplier.is_deleted or supplier.status != Supplier.STATUS_ACTIVE):
            raise ValidationError({"supplier": "Selected supplier is inactive or deleted."})

        if operator and (operator.is_deleted or operator.status != Employee.STATUS_ACTIVE):
            raise ValidationError({"operator": "Selected operator is inactive or deleted."})

        # 5. Payment Method & Account Validation
        if payment_method not in dict(FuelEntry.PAYMENT_METHOD_CHOICES):
            raise ValidationError({"payment_method": "Invalid payment method."})

        if payment_method != FuelEntry.METHOD_CREDIT:
            if not account or account.is_deleted or not account.is_active:
                raise ValidationError({"account": "A valid and active account is required for non-credit fuel payments."})
        else:
            account = None

        entry_date = date_val or timezone.now().date()
        fuel_category = cls.get_or_create_fuel_category(fuel_type)

        # 6. Atomic Execution
        with transaction.atomic():
            # Lock machine for update
            locked_machine = Machine.objects.select_for_update().get(id=machine.id)

            fuel_code = cls.generate_fuel_code(entry_date)

            # Create 1:1 Linked Financial Expense via authoritative ExpenseService
            expense_desc = f"Fuel Log {fuel_code}: {quantity}L {fuel_type} @ ₹{unit_price}/L for {locked_machine.name}"
            if notes:
                expense_desc += f" - {notes}"

            expense, _ = ExpenseService.create_expense(
                user=user,
                amount=total_amount,
                category=fuel_category,
                account=account,
                payment_method=payment_method,
                business_segment=Expense.SEGMENT_MACHINERY_RENTAL if 'RENTAL' in locked_machine.machine_code else Expense.SEGMENT_FARM_OPERATIONS,
                expense_date=entry_date,
                machine=locked_machine,
                employee=operator,
                supplier=supplier,
                reference_no=reference_no,
                description=expense_desc,
                is_quick_expense=False,
                request=request
            )

            # Create FuelEntry
            fuel_entry = FuelEntry.objects.create(
                fuel_code=fuel_code,
                date=entry_date,
                machine=locked_machine,
                fuel_type=fuel_type,
                quantity=quantity,
                unit_price=unit_price,
                total_amount=total_amount,
                supplier=supplier,
                account=account,
                payment_method=payment_method,
                operator=operator,
                meter_reading=meter_reading,
                linked_expense=expense,
                reference_no=reference_no,
                notes=notes,
                created_by=user
            )

            # Update Machine meter reading if higher
            if meter_reading > locked_machine.current_meter_reading:
                locked_machine.current_meter_reading = meter_reading
                locked_machine.save(update_fields=['current_meter_reading', 'updated_at'])

            # Log Audit Trail
            log_audit_event(
                user,
                AuditLog.ACTION_CREATE,
                'FuelEntry',
                fuel_entry.id,
                changes={
                    'fuel_code': fuel_entry.fuel_code,
                    'machine': locked_machine.name,
                    'fuel_type': fuel_type,
                    'quantity': str(quantity),
                    'total_amount': str(total_amount),
                    'meter_reading': str(meter_reading)
                },
                request=request
            )

            return fuel_entry

    @classmethod
    def reverse_fuel_entry(
        cls,
        fuel_entry_id: int,
        user: User,
        reason: str,
        request = None
    ) -> FuelEntry:
        """
        Reverses the financial impact of a fuel entry via Expense reversal.
        """
        profile = getattr(user, 'profile', None)
        is_owner = getattr(profile, 'is_owner', False) if profile else False
        if not is_owner and not getattr(user, 'is_superuser', False):
            raise ValidationError("Reversing fuel transactions is restricted to system Owners.")

        with transaction.atomic():
            fuel_entry = FuelEntry.objects.select_for_update().get(id=fuel_entry_id, is_deleted=False)
            
            # Reverse linked expense
            ExpenseService.reverse_expense(
                expense_id=fuel_entry.linked_expense.id,
                user=user,
                reason=f"Fuel Reversal ({fuel_entry.fuel_code}): {reason}",
                request=request
            )

            log_audit_event(
                user,
                AuditLog.ACTION_REVERSAL,
                'FuelEntry',
                fuel_entry.id,
                changes={'fuel_code': fuel_entry.fuel_code, 'reason': reason},
                request=request
            )

            return fuel_entry
