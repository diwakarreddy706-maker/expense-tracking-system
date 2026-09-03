"""
Farmer Account Statement / Passbook PDF Generator.
Generates an official, auditable A4 statement of accounts for farmers and agricultural clients.
Strictly read-only; consumes authoritative Customer, MachineWorkEntry, and CustomerPayment records.
"""

from decimal import Decimal
from typing import Optional, List, Dict, Any
from django.db.models import Sum, F
from django.utils import timezone
from django.http import HttpResponse

from reportlab.lib import colors
from reportlab.platypus import (
    Paragraph, Table, TableStyle, Spacer, KeepTogether, HRFlowable
)

from apps.finance.models import Customer, Receivable, CustomerPayment
from apps.machines.models import MachineWorkEntry
from apps.reports.services.pdf_service import (
    PDFReportBuilder, COLOR_HEADER_BG, COLOR_BG_LIGHT, COLOR_BG_ZEBRA,
    COLOR_BORDER, COLOR_EMERALD, COLOR_ROSE, COLOR_PRIMARY_DARK, COLOR_TEXT_MUTED
)
from apps.reports.services.audit_service import ReportAuditService


class FarmerStatementPDFService:
    """
    Builds the official Farmer Account Statement / Passbook A4 PDF document.
    """

    @classmethod
    def generate_pdf(
        cls,
        customer_id: int,
        user=None,
        start_date=None,
        end_date=None
    ) -> HttpResponse:
        customer = Customer.objects.get(id=customer_id, is_deleted=False)
        styles = PDFReportBuilder.get_styles()
        elements = []
        usable_w = 523.0  # A4 portrait width (595) - 2 * 36pt margins

        # 1. Company Letterhead & Metadata
        period_str = f"{PDFReportBuilder.format_date(start_date)} to {PDFReportBuilder.format_date(end_date)}" if (start_date or end_date) else "Complete Account History"
        as_of_str = PDFReportBuilder.format_date(timezone.now().date())
        user_name = user.get_full_name() or user.username if user else "Office Administrator"

        letterhead = PDFReportBuilder.create_letterhead(
            report_title="FARMER ACCOUNT STATEMENT / PASSBOOK",
            period_str=period_str,
            as_of_str=as_of_str,
            generated_by_user=user_name,
            version="v1.0",
            usable_width=usable_w
        )
        elements.append(letterhead)
        elements.append(Spacer(1, 10))

        # 2. Farmer Profile Box
        farmer_code = customer.customer_code
        farmer_name = customer.name
        farmer_phone = customer.phone or "--"
        farmer_addr = customer.location_address or "Local Field / Village"

        profile_table = Table([
            [
                [
                    Paragraph("<b>FARMER / CLIENT DETAILS</b>", styles['BodyTextBold']),
                    Paragraph(f"Name: <b>{farmer_name}</b>", styles['BodyText']),
                    Paragraph(f"Farmer ID: <b>{farmer_code}</b>", styles['BodyText']),
                ],
                [
                    Paragraph("<b>LOCATION &amp; CONTACT</b>", styles['BodyTextBold']),
                    Paragraph(f"Mobile: <b>{farmer_phone}</b>", styles['BodyText']),
                    Paragraph(f"Village / Area: <b>{farmer_addr}</b>", styles['BodyText']),
                ]
            ]
        ], colWidths=[usable_w * 0.50, usable_w * 0.50])
        profile_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), COLOR_BG_LIGHT),
            ('BOX', (0, 0), (-1, -1), 1, COLOR_BORDER),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('LEFTPADDING', (0, 0), (-1, -1), 8),
            ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ]))
        elements.append(profile_table)
        elements.append(Spacer(1, 10))

        # 3. Calculate Authoritative Financial Totals
        work_qs = MachineWorkEntry.objects.filter(
            customer=customer,
            is_deleted=False
        ).select_related('machine', 'operator').order_by('work_date', 'id')

        payment_qs = CustomerPayment.objects.filter(
            receivable__customer=customer,
            receivable__is_deleted=False
        ).select_related('account', 'receivable').order_by('payment_date', 'id')

        if start_date:
            work_qs = work_qs.filter(work_date__gte=start_date)
            payment_qs = payment_qs.filter(payment_date__gte=start_date)
        if end_date:
            work_qs = work_qs.filter(work_date__lte=end_date)
            payment_qs = payment_qs.filter(payment_date__lte=end_date)

        total_billed = work_qs.aggregate(s=Sum('total_amount'))['s'] or Decimal('0.00')
        total_advances = work_qs.aggregate(s=Sum('advance_amount'))['s'] or Decimal('0.00')
        total_direct_payments = payment_qs.aggregate(s=Sum('amount'))['s'] or Decimal('0.00')
        total_paid = total_advances + total_direct_payments

        # Total outstanding Udhar from customer receivables
        unpaid_recs = customer.receivables.filter(is_deleted=False).exclude(status='PAID')
        outstanding_udhar = sum((r.total_amount - r.received_amount for r in unpaid_recs), Decimal('0.00'))

        # 4. Financial Summary Cards
        kpi_box = PDFReportBuilder.create_kpi_summary_box([
            ("Total Work Billed", PDFReportBuilder.format_inr(total_billed), COLOR_PRIMARY_DARK),
            ("Advances Paid", PDFReportBuilder.format_inr(total_advances), COLOR_EMERALD),
            ("Direct Paid", PDFReportBuilder.format_inr(total_direct_payments), COLOR_EMERALD),
            ("Total Settled", PDFReportBuilder.format_inr(total_paid), COLOR_EMERALD),
            ("Balance Due (Udhar)", PDFReportBuilder.format_inr(outstanding_udhar), COLOR_ROSE),
        ], usable_width=usable_w)
        elements.append(kpi_box)
        elements.append(Spacer(1, 12))

        # 5. Build Chronological Combined Ledger Statement
        statement_events = []

        # Ingest Work Entries (Debits)
        for w in work_qs:
            usage_str = f"{w.net_working_hours} hrs" if w.billing_type == MachineWorkEntry.BILLING_TIME_HOURLY else f"{w.quantity} {w.get_billing_type_display()}"
            desc = f"Work: {w.machine.name} ({usage_str})"
            if w.manual_bill_no:
                desc += f" [Bill #{w.manual_bill_no}]"

            statement_events.append({
                'date': w.work_date,
                'id': w.id,
                'type': 'WORK',
                'code': w.manual_bill_no or w.work_code,
                'description': desc,
                'machine': w.machine.name,
                'debit': w.total_amount,
                'credit': Decimal('0.00'),
            })

            # If advance was collected on the field for this work entry
            if w.advance_amount and w.advance_amount > Decimal('0.00'):
                statement_events.append({
                    'date': w.work_date,
                    'id': w.id,
                    'type': 'ADVANCE',
                    'code': f"ADV-{w.manual_bill_no or w.work_code}",
                    'description': f"On-Site Advance for {w.work_code}",
                    'machine': w.machine.name,
                    'debit': Decimal('0.00'),
                    'credit': w.advance_amount,
                })

        # Ingest Direct Payments (Credits)
        for p in payment_qs:
            ref_str = f" [Ref: {p.reference_no}]" if p.reference_no else ""
            statement_events.append({
                'date': p.payment_date,
                'id': p.id,
                'type': 'PAYMENT',
                'code': p.payment_code,
                'description': f"Settlement via {p.get_payment_method_display()}{ref_str}",
                'machine': "--",
                'debit': Decimal('0.00'),
                'credit': p.amount,
            })

        # Sort Chronologically (date, then type so work comes before advance/payment on same date)
        statement_events.sort(key=lambda x: (x['date'], 0 if x['type'] == 'WORK' else 1, x['id']))

        # Compute Running Balance
        running_bal = Decimal('0.00')
        table_rows = [
            [
                Paragraph("<b>DATE</b>", styles['TableHeaderCenter']),
                Paragraph("<b>VOUCHER / CODE</b>", styles['TableHeader']),
                Paragraph("<b>DESCRIPTION &amp; DETAILS</b>", styles['TableHeader']),
                Paragraph("<b>MACHINE</b>", styles['TableHeader']),
                Paragraph("<b>BILL (DEBIT)</b>", styles['TableHeaderRight']),
                Paragraph("<b>PAID (CREDIT)</b>", styles['TableHeaderRight']),
                Paragraph("<b>BALANCE</b>", styles['TableHeaderRight']),
            ]
        ]

        for ev in statement_events:
            running_bal += (ev['debit'] - ev['credit'])
            debit_str = PDFReportBuilder.format_inr(ev['debit'], show_symbol=False) if ev['debit'] > 0 else "--"
            credit_str = PDFReportBuilder.format_inr(ev['credit'], show_symbol=False) if ev['credit'] > 0 else "--"
            bal_str = PDFReportBuilder.format_inr(running_bal, show_symbol=False)

            table_rows.append([
                Paragraph(PDFReportBuilder.format_date(ev['date']), styles['TableCellCenter']),
                Paragraph(ev['code'], styles['TableCellBold']),
                Paragraph(ev['description'], styles['TableCell']),
                Paragraph(ev['machine'], styles['TableCell']),
                Paragraph(debit_str, styles['TableCellRight']),
                Paragraph(credit_str, styles['TableCellRight']),
                Paragraph(bal_str, styles['TableCellRightBold']),
            ])

        if not statement_events:
            table_rows.append([
                Paragraph("--", styles['TableCellCenter']),
                Paragraph("NO_RECORDS", styles['TableCell']),
                Paragraph("No work sessions or payment settlements recorded for this farmer.", styles['TableCell']),
                Paragraph("--", styles['TableCell']),
                Paragraph("--", styles['TableCellRight']),
                Paragraph("--", styles['TableCellRight']),
                Paragraph(PDFReportBuilder.format_inr(Decimal('0.00'), show_symbol=False), styles['TableCellRightBold']),
            ])

        # Table Geometry: Sum = 523pt
        col_w = [55, 75, 163, 65, 55, 55, 55]
        stmt_table = Table(table_rows, colWidths=col_w, repeatRows=1)

        t_style = [
            ('BACKGROUND', (0, 0), (-1, 0), COLOR_HEADER_BG),
            ('BOX', (0, 0), (-1, -1), 1, COLOR_BORDER),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, COLOR_BORDER),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('LEFTPADDING', (0, 0), (-1, -1), 4),
            ('RIGHTPADDING', (0, 0), (-1, -1), 4),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]

        # Zebra striping
        for i in range(1, len(table_rows)):
            if i % 2 == 0:
                t_style.append(('BACKGROUND', (0, i), (-1, i), COLOR_BG_ZEBRA))
            else:
                t_style.append(('BACKGROUND', (0, i), (-1, i), colors.white))

        stmt_table.setStyle(TableStyle(t_style))
        elements.append(stmt_table)
        elements.append(Spacer(1, 15))

        # 6. Formal Signature Block
        sig_block = PDFReportBuilder.create_signature_block(usable_width=usable_w)
        elements.append(KeepTogether([sig_block]))

        # 7. Audit Logging
        filename = f"farmer_statement_{customer.customer_code}_{timezone.now().strftime('%Y%m%d')}.pdf"
        ReportAuditService.log_report_generation(
            report_type=ReportAuditService.TYPE_FARMER_STATEMENT,
            user=user,
            related_object_id=customer.id,
            period_start=start_date,
            period_end=end_date,
            file_name=filename,
            metadata={'customer_code': customer.customer_code, 'customer_name': customer.name}
        )

        return PDFReportBuilder.build_pdf_response(elements, filename=filename, orientation='portrait')
