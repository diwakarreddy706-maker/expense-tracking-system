"""
Authoritative Master Data CSV Import & Production Onboarding Service.
Provides strict validation, duplicate detection, dry-run previews,
atomic database persistence, and template generation for real business onboarding.
"""

import csv
import io
from decimal import Decimal, InvalidOperation
from typing import Dict, Any, List, Tuple
from django.db import transaction
from django.utils import timezone
from django.contrib.auth.models import User

from apps.finance.models import Account, Customer, Supplier, Receivable, Payable
from apps.machines.models import Machine, MachineType
from apps.employees.models import Employee, EmployeeCompensation
from apps.expenses.models import ExpenseCategory


class MasterDataImportService:
    """
    Service responsible for validating and importing business master data via CSV.
    Operates strictly within database transactions and enforces all model constraints.
    """

    SUPPORTED_ENTITIES = ['machines', 'customers', 'suppliers', 'employees', 'accounts']

    SCHEMAS = {
        'machines': {
            'headers': ['machine_code', 'name', 'machine_type', 'registration_no', 'current_meter_reading', 'meter_unit', 'purchase_price', 'status'],
            'required': ['name', 'machine_type'],
            'sample': [
                ['MCH-001', 'John Deere 5310 4WD', 'TRACTOR', 'AP21-TR-9081', '1250.50', 'HOURS', '950000.00', 'ACTIVE'],
                ['MCH-002', 'Kubota Harvester DC-68G', 'PADDY_HARVESTER', 'AP21-HV-4112', '450.00', 'HOURS', '2400000.00', 'ACTIVE']
            ]
        },
        'customers': {
            'headers': ['customer_code', 'name', 'phone', 'location_address', 'opening_balance', 'notes'],
            'required': ['name'],
            'sample': [
                ['CUST-001', 'Ramesh Patel', '9876543210', 'Navalgund Village, Sector 3', '15000.00', 'Regular paddy farmer'],
                ['CUST-002', 'Suresh Kumar Reddy', '9848012345', 'Anantapur Rural', '0.00', 'Cotton farming client']
            ]
        },
        'suppliers': {
            'headers': ['supplier_code', 'name', 'supplier_type', 'phone', 'location_address', 'payment_terms', 'opening_balance', 'notes'],
            'required': ['name', 'supplier_type'],
            'sample': [
                ['SUPP-001', 'Sri Lakshmi Indian Oil Pump', 'FUEL_PUMP', '9440112233', 'NH-44 Bypass, Kurnool', 'Weekly Credit', '28500.00', 'Primary diesel supplier'],
                ['SUPP-002', 'Balaji Spares & Agro Workshop', 'SPARE_PARTS', '9885023456', 'Industrial Area, Hubli', '30 Days Net', '12000.00', 'Harvester blades & belts']
            ]
        },
        'employees': {
            'headers': ['employee_code', 'full_name', 'role', 'phone_number', 'wage_type', 'base_rate', 'emergency_contact'],
            'required': ['full_name', 'role', 'wage_type', 'base_rate'],
            'sample': [
                ['EMP-001', 'Venkataiah G', 'TRACTOR_DRIVER', '9701234567', 'DAILY_WAGE', '600.00', '9876543210'],
                ['EMP-002', 'Mohammad Rafi', 'HARVESTER_OPERATOR', '9849123456', 'PER_ACRE_COMMISSION', '180.00', '9123456789'],
                ['EMP-003', 'Anil Kumar', 'ACCOUNTANT', '9988776655', 'MONTHLY_SALARY', '25000.00', '9876501234']
            ]
        },
        'accounts': {
            'headers': ['account_name', 'account_type', 'bank_name', 'account_number', 'ifsc_code', 'opening_balance'],
            'required': ['account_name', 'account_type'],
            'sample': [
                ['Main Cash Box', 'CASH', '', '', '', '25000.00'],
                ['SBI Operating Account', 'BANK_CURRENT', 'State Bank of India', '38291048291', 'SBIN0001234', '150000.00'],
                ['HDFC Business Savings', 'BANK_SAVINGS', 'HDFC Bank', '501002394819', 'HDFC0000456', '75000.00'],
                ['Business PhonePe / UPI', 'UPI_WALLET', 'Yes Bank UPI', 'agribos@upi', '', '5000.00']
            ]
        }
    }

    @classmethod
    def generate_csv_template(cls, entity_type: str) -> str:
        """
        Generates standard UTF-8 CSV template string with headers and sample rows.
        """
        if entity_type not in cls.SCHEMAS:
            raise ValueError(f"Unsupported entity type '{entity_type}'. Must be one of {cls.SUPPORTED_ENTITIES}")

        schema = cls.SCHEMAS[entity_type]
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(schema['headers'])
        for row in schema['sample']:
            writer.writerow(row)
        return output.getvalue()

    @classmethod
    def parse_and_validate(cls, entity_type: str, file_obj) -> Dict[str, Any]:
        """
        Parses CSV input, validates every row against domain rules, checks for duplicates,
        and returns a structured validation preview without persisting records to the database.
        """
        if entity_type not in cls.SCHEMAS:
            return {
                'success': False,
                'error': f"Unsupported entity type: '{entity_type}'",
                'total_rows': 0,
                'valid_rows_count': 0,
                'invalid_rows_count': 0,
                'preview_rows': [],
                'errors': [f"Entity type must be one of {', '.join(cls.SUPPORTED_ENTITIES)}"]
            }

        schema = cls.SCHEMAS[entity_type]
        expected_headers = schema['headers']
        required_fields = schema['required']

        try:
            content = file_obj.read()
            if isinstance(content, bytes):
                try:
                    decoded = content.decode('utf-8-sig')  # Handles UTF-8 with or without BOM
                except UnicodeDecodeError:
                    decoded = content.decode('latin-1')
            else:
                decoded = content

            io_string = io.StringIO(decoded)
            reader = csv.DictReader(io_string)
        except Exception as e:
            return {
                'success': False,
                'error': f"Failed to parse CSV file: {str(e)}",
                'total_rows': 0,
                'valid_rows_count': 0,
                'invalid_rows_count': 0,
                'preview_rows': [],
                'errors': ["Invalid CSV format or character encoding."]
            }

        if not reader.fieldnames:
            return {
                'success': False,
                'error': "CSV file appears to be empty.",
                'total_rows': 0,
                'valid_rows_count': 0,
                'invalid_rows_count': 0,
                'preview_rows': [],
                'errors': ["File header row is missing."]
            }

        # Validate headers
        normalized_fieldnames = [str(f).strip().lower() for f in reader.fieldnames if f]
        missing_req: List[str] = [str(rf) for rf in required_fields if str(rf).lower() not in normalized_fieldnames]
        if missing_req:
            return {
                'success': False,
                'error': f"Missing required CSV column headers: {', '.join(missing_req)}",
                'total_rows': 0,
                'valid_rows_count': 0,
                'invalid_rows_count': 0,
                'preview_rows': [],
                'errors': [f"Missing required columns: {missing_req}. Required header schema: {expected_headers}"]
            }

        preview_rows = []
        errors = []
        seen_codes = set()
        seen_names = set()
        row_num = 1  # 1 is header

        # Fetch existing unique keys for pre-validation
        existing_machine_codes = set(Machine.objects.filter(is_deleted=False).values_list('machine_code', flat=True))
        existing_reg_nos = set(Machine.objects.filter(is_deleted=False, registration_no__isnull=False).values_list('registration_no', flat=True))
        existing_cust_codes = set(Customer.objects.filter(is_deleted=False).values_list('customer_code', flat=True))
        existing_supp_codes = set(Supplier.objects.filter(is_deleted=False).values_list('supplier_code', flat=True))
        existing_emp_codes = set(Employee.objects.filter(is_deleted=False).values_list('employee_code', flat=True))
        existing_account_names = set(Account.objects.filter(is_deleted=False).values_list('account_name', flat=True))

        for raw_row in reader:
            row_num += 1
            # Clean keys & values
            row = {k.strip().lower(): (v.strip() if v else '') for k, v in raw_row.items() if k}
            if not any(row.values()):
                continue  # skip empty lines

            row_errors = []
            cleaned_data = {}

            # --- ENTITY SPECIFIC VALIDATION ---
            if entity_type == 'machines':
                code = row.get('machine_code') or f"MCH-{row_num:03d}"
                name = row.get('name', '')
                m_type = row.get('machine_type', '').upper()
                reg_no = row.get('registration_no', '')
                meter_str = row.get('current_meter_reading', '0.00')
                meter_unit = row.get('meter_unit', 'HOURS').upper()
                price_str = row.get('purchase_price', '0.00')
                status = row.get('status', 'ACTIVE').upper()

                if not name:
                    row_errors.append("Machine name/model is required.")
                if not m_type:
                    row_errors.append("Machine type is required.")
                else:
                    # Check or map machine type
                    type_obj = MachineType.objects.filter(code=m_type).first() or MachineType.objects.filter(name__iexact=m_type).first()
                    if not type_obj:
                        valid_types = list(MachineType.objects.values_list('code', flat=True))
                        row_errors.append(f"Invalid machine type '{m_type}'. Valid: {', '.join(valid_types)}")

                if code in seen_codes:
                    row_errors.append(f"Duplicate machine code '{code}' within CSV file.")
                elif code in existing_machine_codes:
                    row_errors.append(f"Machine code '{code}' already exists in database.")
                seen_codes.add(code)

                if reg_no:
                    if reg_no in seen_names:
                        row_errors.append(f"Duplicate registration number '{reg_no}' within CSV.")
                    elif reg_no in existing_reg_nos:
                        row_errors.append(f"Registration number '{reg_no}' already registered in database.")
                    seen_names.add(reg_no)

                try:
                    meter_val = Decimal(meter_str) if meter_str else Decimal('0.00')
                    if meter_val < 0:
                        row_errors.append("Meter reading cannot be negative.")
                except (InvalidOperation, ValueError):
                    row_errors.append(f"Invalid numeric meter reading: '{meter_str}'.")
                    meter_val = Decimal('0.00')

                try:
                    price_val = Decimal(price_str) if price_str else None
                    if price_val is not None and price_val < 0:
                        row_errors.append("Purchase price cannot be negative.")
                except (InvalidOperation, ValueError):
                    row_errors.append(f"Invalid purchase price: '{price_str}'.")
                    price_val = None

                valid_statuses = [c[0] for c in Machine.STATUS_CHOICES]
                if status not in valid_statuses:
                    status = 'ACTIVE'

                valid_units = [c[0] for c in Machine.METER_UNIT_CHOICES]
                if meter_unit not in valid_units:
                    meter_unit = 'HOURS'

                cleaned_data = {
                    'machine_code': code,
                    'name': name,
                    'machine_type': m_type,
                    'registration_no': reg_no,
                    'current_meter_reading': str(meter_val),
                    'meter_unit': meter_unit,
                    'purchase_price': str(price_val) if price_val else '',
                    'status': status
                }

            elif entity_type == 'customers':
                code = row.get('customer_code') or f"CUST-{row_num:04d}"
                name = row.get('name', '')
                phone = row.get('phone', '')
                address = row.get('location_address', '')
                op_bal_str = row.get('opening_balance', '0.00')
                notes = row.get('notes', '')

                if not name:
                    row_errors.append("Customer name is required.")
                if code in seen_codes:
                    row_errors.append(f"Duplicate customer code '{code}' in CSV.")
                elif code in existing_cust_codes:
                    row_errors.append(f"Customer code '{code}' already exists in database.")
                seen_codes.add(code)

                try:
                    op_bal = Decimal(op_bal_str) if op_bal_str else Decimal('0.00')
                    if op_bal < 0:
                        row_errors.append("Opening balance cannot be negative.")
                except (InvalidOperation, ValueError):
                    row_errors.append(f"Invalid opening balance amount: '{op_bal_str}'.")
                    op_bal = Decimal('0.00')

                cleaned_data = {
                    'customer_code': code,
                    'name': name,
                    'phone': phone,
                    'location_address': address,
                    'opening_balance': str(op_bal),
                    'notes': notes
                }

            elif entity_type == 'suppliers':
                code = row.get('supplier_code') or f"SUPP-{row_num:04d}"
                name = row.get('name', '')
                s_type = row.get('supplier_type', 'OTHER').upper()
                phone = row.get('phone', '')
                address = row.get('location_address', '')
                terms = row.get('payment_terms', '')
                op_bal_str = row.get('opening_balance', '0.00')
                notes = row.get('notes', '')

                if not name:
                    row_errors.append("Supplier name is required.")

                valid_types = [c[0] for c in Supplier.SUPPLIER_TYPE_CHOICES]
                if s_type not in valid_types:
                    row_errors.append(f"Invalid supplier type '{s_type}'. Valid: {', '.join(valid_types)}")

                if code in seen_codes:
                    row_errors.append(f"Duplicate supplier code '{code}' in CSV.")
                elif code in existing_supp_codes:
                    row_errors.append(f"Supplier code '{code}' already exists in database.")
                seen_codes.add(code)

                try:
                    op_bal = Decimal(op_bal_str) if op_bal_str else Decimal('0.00')
                    if op_bal < 0:
                        row_errors.append("Opening balance cannot be negative.")
                except (InvalidOperation, ValueError):
                    row_errors.append(f"Invalid opening balance amount: '{op_bal_str}'.")
                    op_bal = Decimal('0.00')

                cleaned_data = {
                    'supplier_code': code,
                    'name': name,
                    'supplier_type': s_type,
                    'phone': phone,
                    'location_address': address,
                    'payment_terms': terms,
                    'opening_balance': str(op_bal),
                    'notes': notes
                }

            elif entity_type == 'employees':
                code = row.get('employee_code') or f"EMP-{row_num:03d}"
                name = row.get('full_name', '')
                role = row.get('role', 'TRACTOR_DRIVER').upper()
                phone = row.get('phone_number', '')
                wage_type = row.get('wage_type', 'DAILY_WAGE').upper()
                rate_str = row.get('base_rate', '0.00')
                emergency = row.get('emergency_contact', '')

                if not name:
                    row_errors.append("Employee full name is required.")

                valid_roles = [c[0] for c in Employee.ROLE_CHOICES]
                if role not in valid_roles:
                    row_errors.append(f"Invalid employee role '{role}'. Valid: {', '.join(valid_roles)}")

                valid_wages = [c[0] for c in EmployeeCompensation.WAGE_TYPE_CHOICES]
                if wage_type not in valid_wages:
                    row_errors.append(f"Invalid wage type '{wage_type}'. Valid: {', '.join(valid_wages)}")

                if code in seen_codes:
                    row_errors.append(f"Duplicate employee code '{code}' in CSV.")
                elif code in existing_emp_codes:
                    row_errors.append(f"Employee code '{code}' already exists in database.")
                seen_codes.add(code)

                try:
                    rate_val = Decimal(rate_str) if rate_str else Decimal('0.00')
                    if rate_val < 0:
                        row_errors.append("Wage rate cannot be negative.")
                except (InvalidOperation, ValueError):
                    row_errors.append(f"Invalid wage rate amount: '{rate_str}'.")
                    rate_val = Decimal('0.00')

                cleaned_data = {
                    'employee_code': code,
                    'full_name': name,
                    'role': role,
                    'phone_number': phone,
                    'wage_type': wage_type,
                    'base_rate': str(rate_val),
                    'emergency_contact': emergency
                }

            elif entity_type == 'accounts':
                name = row.get('account_name', '')
                a_type = row.get('account_type', 'BANK_CURRENT').upper()
                bank = row.get('bank_name', '')
                acc_num = row.get('account_number', '')
                ifsc = row.get('ifsc_code', '')
                op_bal_str = row.get('opening_balance', '0.00')

                if not name:
                    row_errors.append("Account name is required.")
                if name.lower() in seen_names:
                    row_errors.append(f"Duplicate account name '{name}' in CSV file.")
                elif name in existing_account_names:
                    row_errors.append(f"Account name '{name}' already exists in database.")
                seen_names.add(name.lower())

                valid_types = [c[0] for c in Account.ACCOUNT_TYPE_CHOICES]
                if a_type not in valid_types:
                    row_errors.append(f"Invalid account type '{a_type}'. Valid: {', '.join(valid_types)}")

                try:
                    op_bal = Decimal(op_bal_str) if op_bal_str else Decimal('0.00')
                    if op_bal < 0:
                        row_errors.append("Opening balance cannot be negative.")
                except (InvalidOperation, ValueError):
                    row_errors.append(f"Invalid opening balance: '{op_bal_str}'.")
                    op_bal = Decimal('0.00')

                cleaned_data = {
                    'account_name': name,
                    'account_type': a_type,
                    'bank_name': bank,
                    'account_number': acc_num,
                    'ifsc_code': ifsc,
                    'opening_balance': str(op_bal)
                }

            is_valid = len(row_errors) == 0
            if row_errors:
                errors.append(f"Row {row_num}: {'; '.join(row_errors)}")

            preview_rows.append({
                'row_number': row_num,
                'data': cleaned_data,
                'is_valid': is_valid,
                'errors': row_errors
            })

        total_rows = len(preview_rows)
        valid_rows_count = sum(1 for r in preview_rows if r['is_valid'])
        invalid_rows_count = total_rows - valid_rows_count

        return {
            'success': True,
            'entity_type': entity_type,
            'total_rows': total_rows,
            'valid_rows_count': valid_rows_count,
            'invalid_rows_count': invalid_rows_count,
            'is_ready_for_import': (total_rows > 0 and invalid_rows_count == 0),
            'preview_rows': preview_rows,
            'errors': errors
        }

    @classmethod
    @transaction.atomic
    def execute_import(cls, entity_type: str, preview_data: List[Dict[str, Any]], user: User) -> Dict[str, Any]:
        """
        Executes atomic database insertion for validated preview rows.
        Guarantees that invalid records are never partially imported.
        """
        if not preview_data:
            return {'success': False, 'message': 'No data rows provided for import.'}

        created_records = []
        opening_records_created = 0

        for item in preview_data:
            data = item.get('data', {})
            if not item.get('is_valid', True):
                raise ValueError(f"Cannot import invalid row {item.get('row_number')}: {item.get('errors')}")

            if entity_type == 'machines':
                m_type = MachineType.objects.filter(code=data['machine_type']).first() or MachineType.objects.filter(name__iexact=data['machine_type']).first()
                if not m_type:
                    m_type, _ = MachineType.objects.get_or_create(code=data['machine_type'], defaults={'name': data['machine_type'].title()})

                price = Decimal(data['purchase_price']) if data.get('purchase_price') else None
                m = Machine.objects.create(
                    machine_code=data['machine_code'],
                    name=data['name'],
                    machine_type=m_type,
                    registration_no=data.get('registration_no') or None,
                    current_meter_reading=Decimal(data.get('current_meter_reading', '0.00')),
                    meter_unit=data.get('meter_unit', 'HOURS'),
                    purchase_price=price,
                    status=data.get('status', 'ACTIVE')
                )
                created_records.append(f"{m.machine_code} ({m.name})")

            elif entity_type == 'customers':
                cust = Customer.objects.create(
                    customer_code=data['customer_code'],
                    name=data['name'],
                    phone=data.get('phone') or None,
                    location_address=data.get('location_address') or None,
                    notes=data.get('notes') or None,
                    status=Customer.STATUS_ACTIVE
                )
                op_bal = Decimal(data.get('opening_balance', '0.00'))
                if op_bal > Decimal('0.00'):
                    # Create opening receivable without phantom revenue
                    Receivable.objects.create(
                        receivable_code=f"REC-OP-{cust.customer_code}",
                        customer=cust,
                        invoice_no="OPENING-BAL",
                        bill_date=timezone.now().date(),
                        total_amount=op_bal,
                        received_amount=Decimal('0.00'),
                        status=Receivable.STATUS_UNPAID,
                        notes=f"Opening Receivable Due recorded on onboarding for {cust.name}",
                        created_by=user
                    )
                    opening_records_created += 1
                created_records.append(f"{cust.customer_code} ({cust.name})")

            elif entity_type == 'suppliers':
                supp = Supplier.objects.create(
                    supplier_code=data['supplier_code'],
                    name=data['name'],
                    supplier_type=data.get('supplier_type', Supplier.TYPE_OTHER),
                    phone=data.get('phone') or None,
                    location_address=data.get('location_address') or None,
                    payment_terms=data.get('payment_terms') or None,
                    notes=data.get('notes') or None,
                    status=Supplier.STATUS_ACTIVE
                )
                op_bal = Decimal(data.get('opening_balance', '0.00'))
                if op_bal > Decimal('0.00'):
                    # Create opening payable without phantom expense
                    Payable.objects.create(
                        payable_code=f"PAY-OP-{supp.supplier_code}",
                        supplier=supp,
                        bill_no="OPENING-BAL",
                        bill_date=timezone.now().date(),
                        total_amount=op_bal,
                        paid_amount=Decimal('0.00'),
                        status=Payable.STATUS_UNPAID,
                        notes=f"Opening Payable Due recorded on onboarding for {supp.name}",
                        created_by=user
                    )
                    opening_records_created += 1
                created_records.append(f"{supp.supplier_code} ({supp.name})")

            elif entity_type == 'employees':
                emp = Employee.objects.create(
                    employee_code=data['employee_code'],
                    full_name=data['full_name'],
                    role=data.get('role', Employee.ROLE_TRACTOR_DRIVER),
                    phone_number=data.get('phone_number') or None,
                    wage_type=data.get('wage_type', Employee.WAGE_DAILY),
                    base_rate=Decimal(data.get('base_rate', '0.00')),
                    emergency_contact=data.get('emergency_contact') or None,
                    status=Employee.STATUS_ACTIVE
                )
                # Create authoritative EmployeeCompensation record
                EmployeeCompensation.objects.create(
                    employee=emp,
                    wage_type=data.get('wage_type', Employee.WAGE_DAILY),
                    rate=Decimal(data.get('base_rate', '0.00')),
                    effective_from=timezone.now().date(),
                    is_active=True
                )
                created_records.append(f"{emp.employee_code} ({emp.full_name})")

            elif entity_type == 'accounts':
                op_bal = Decimal(data.get('opening_balance', '0.00'))
                acc = Account.objects.create(
                    account_name=data['account_name'],
                    account_type=data.get('account_type', Account.TYPE_BANK_CURRENT),
                    bank_name=data.get('bank_name') or None,
                    account_number=data.get('account_number') or None,
                    ifsc_code=data.get('ifsc_code') or None,
                    opening_balance=op_bal,
                    current_balance=op_bal,
                    is_active=True
                )
                created_records.append(f"{acc.account_name} ({acc.get_account_type_display()})")

        return {
            'success': True,
            'imported_count': len(created_records),
            'opening_records_created': opening_records_created,
            'records': created_records,
            'message': f"Successfully imported {len(created_records)} {entity_type} record(s)."
        }
