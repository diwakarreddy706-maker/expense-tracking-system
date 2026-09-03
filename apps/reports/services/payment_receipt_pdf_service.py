"""
Payment / Advance Receipt PDF Generator.
Generates an official, auditable A4 receipt voucher for farmer debt collections, advances, and bank transfers.
Strictly read-only; consumes authoritative CustomerPayment and Account records.
"""

from decimal import Decimal
from typing import Optional
from django.utils import timezone
from django.http import HttpResponse

from reportlab.lib import colors
from reportlab.platypus import (
    Paragraph, Table, TableStyle, Spacer, KeepTogether, HRFlowable
)

from apps.finance.models import CustomerPayment, Customer, Receivable
from apps.reports.services.pdf_service import (
    PDFReportBuilder, COLOR_HEADER_BG, COLOR_BG_LIGHT, COLOR_BG_ZEBRA,
    COLOR_BORDER, COLOR_EMERALD, COLOR_ROSE, COLOR_PRIMARY_DARK, COLOR_TEXT_MUTED
)
from apps.reports.services.audit_service import ReportAuditService


class PaymentReceiptPDFService:
    """
    Builds the official Payment / Advance Receipt A4 PDF document.
    """

    @classmethod
    def generate_pdf(
        cls,
        payment_id: int,
        user=None
    ) -> HttpResponse:
        payment = CustomerPayment.objects.select_related(
            'receivable', 'receivable__customer', 'account', 'linked_ledger_transaction'
        ).get(id=payment_id)

        customer = payment.receivable.customer
        styles = PDFReportBuilder.get_styles()
        elements = []
        usable_w = 523.0

        # 1. Company Letterhead & Receipt Header
        as_of_str = PDFReportBuilder.format_date(payment.payment_date)
        user_name = user.get_full_name() or user.username if user else "Cashier / Operator"

        letterhead = PDFReportBuilder.create_letterhead(
            report_title="OFFICIAL PAYMENT RECEIPT",
            period_str=None,
            as_of_str=as_of_str,
            generated_by_user=user_name,
            version="v1.0",
            usable_width=usable_w
        )
        elements.append(letterhead)
        elements.append(Spacer(1, 12))

        # 2. Receipt Details Banner
        receipt_box = Table([
            [
                [
                    Paragraph(f"RECEIPT NO: <b>{payment.payment_code}</b>", styles['BodyTextBold']),
                    Paragraph(f"Payment Date: <b>{PDFReportBuilder.format_date(payment.payment_date)}</b>", styles['BodyText']),
                    Paragraph(f"Payment Mode: <b>{payment.get_payment_method_display()}</b>", styles['BodyText']),
                ],
                [
                    Paragraph(f"Received Into: <b>{payment.account.account_name}</b>", styles['BodyText']),
                    Paragraph(f"Transaction Ref: <b>{payment.reference_no or 'Direct Settlement'}</b>", styles['BodyText']),
                    Paragraph(f"Settled Voucher: <b>{payment.receivable.invoice_no or payment.receivable.receivable_code}</b>", styles['BodyText']),
                ]
            ]
        ], colWidths=[usable_w * 0.50, usable_w * 0.50])
        receipt_box.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), COLOR_BG_LIGHT),
            ('BOX', (0, 0), (-1, -1), 1, COLOR_BORDER),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('LEFTPADDING', (0, 0), (-1, -1), 8),
            ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ]))
        elements.append(receipt_box)
        elements.append(Spacer(1, 10))

        # 3. Farmer Payer Details
        farmer_table = Table([
            [
                Paragraph("<b>RECEIVED FROM (FARMER / CLIENT):</b>", styles['BodyTextBold']),
                Paragraph(f"<b>{customer.name}</b> (Farmer Code: {customer.customer_code})", styles['BodyTextBold']),
            ],
            [
                Paragraph("<b>Location / Village:</b>", styles['BodyText']),
                Paragraph(customer.location_address or "Local Field / Village", styles['BodyText']),
            ],
            [
                Paragraph("<b>Contact Phone:</b>", styles['BodyText']),
                Paragraph(customer.phone or "--", styles['BodyText']),
            ],
        ], colWidths=[usable_w * 0.35, usable_w * 0.65])
        farmer_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.white),
            ('BOX', (0, 0), (-1, -1), 0.5, COLOR_BORDER),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
            ('LEFTPADDING', (0, 0), (-1, -1), 8),
            ('RIGHTPADDING', (0, 0), (-1, -1), 8),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, COLOR_BG_ZEBRA),
        ]))
        elements.append(farmer_table)
        elements.append(Spacer(1, 12))

        # 4. Prominent Amount Box
        amount_val = payment.amount
        amount_str = PDFReportBuilder.format_inr(amount_val)

        # Current total balance due
        unpaid_recs = customer.receivables.filter(is_deleted=False).exclude(status='PAID')
        current_balance = sum((r.total_amount - r.received_amount for r in unpaid_recs), Decimal('0.00'))

        summary_kpis = PDFReportBuilder.create_kpi_summary_box([
            ("AMOUNT RECEIVED", amount_str, COLOR_EMERALD),
            ("SETTLED VOUCHER BILL", PDFReportBuilder.format_inr(payment.receivable.total_amount), COLOR_PRIMARY_DARK),
            ("VOUCHER PAID SO FAR", PDFReportBuilder.format_inr(payment.receivable.received_amount), COLOR_EMERALD),
            ("REMAINING FARMER UDHAR", PDFReportBuilder.format_inr(current_balance), COLOR_ROSE),
        ], usable_width=usable_w)
        elements.append(summary_kpis)
        elements.append(Spacer(1, 15))

        # 5. Settlement Details Breakdown Table
        breakdown_table = Table([
            [
                Paragraph("<b>DESCRIPTION / SETTLEMENT PURPOSE</b>", styles['TableHeader']),
                Paragraph("<b>PAYMENT METHOD</b>", styles['TableHeaderCenter']),
                Paragraph("<b>RECEIVED AMOUNT</b>", styles['TableHeaderRight']),
            ],
            [
                Paragraph(f"Settlement of Udhar / Harvesting Bill #{payment.receivable.invoice_no or payment.receivable.receivable_code}", styles['TableCell']),
                Paragraph(payment.get_payment_method_display(), styles['TableCellCenter']),
                Paragraph(amount_str, styles['TableCellRightBold']),
            ],
            [
                Paragraph("<b>TOTAL REVENUE CREDITED TO ACCOUNT</b>", styles['TableCellBold']),
                Paragraph(payment.account.account_name, styles['TableCellCenter']),
                Paragraph(f"<b>{amount_str}</b>", styles['TableCellRightBold']),
            ]
        ], colWidths=[usable_w * 0.55, usable_w * 0.25, usable_w * 0.20])
        breakdown_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), COLOR_HEADER_BG),
            ('BOX', (0, 0), (-1, -1), 1, COLOR_BORDER),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, COLOR_BORDER),
            ('BACKGROUND', (0, 1), (-1, 1), colors.white),
            ('BACKGROUND', (0, 2), (-1, 2), COLOR_BG_LIGHT),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ]))
        elements.append(breakdown_table)
        elements.append(Spacer(1, 20))

        # 6. Authorization Block
        sig_block = PDFReportBuilder.create_signature_block(usable_width=usable_w, signatory_title="Cashier / Accountant")
        elements.append(KeepTogether([sig_block]))

        # 7. Audit Logging
        filename = f"payment_receipt_{payment.payment_code}_{timezone.now().strftime('%Y%m%d')}.pdf"
        ReportAuditService.log_report_generation(
            report_type=ReportAuditService.TYPE_PAYMENT_RECEIPT,
            user=user,
            related_object_id=payment.id,
            as_of_date=payment.payment_date,
            file_name=filename,
            metadata={'payment_code': payment.payment_code, 'amount': str(payment.amount), 'customer': customer.name}
        )

        return PDFReportBuilder.build_pdf_response(elements, filename=filename, orientation='portrait')
