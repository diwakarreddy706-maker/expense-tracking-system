"""
Work Entry / Field Invoice PDF Generator.
Generates an official, auditable A4 invoice voucher for agricultural machine operations.
Strictly read-only; consumes authoritative MachineWorkEntry, Machine, and Customer records.
"""

from decimal import Decimal
from typing import Optional
from django.utils import timezone
from django.http import HttpResponse

from reportlab.lib import colors
from reportlab.platypus import (
    Paragraph, Table, TableStyle, Spacer, KeepTogether, HRFlowable
)

from apps.machines.models import MachineWorkEntry
from apps.reports.services.pdf_service import (
    PDFReportBuilder, COLOR_HEADER_BG, COLOR_BG_LIGHT, COLOR_BG_ZEBRA,
    COLOR_BORDER, COLOR_EMERALD, COLOR_ROSE, COLOR_PRIMARY_DARK, COLOR_TEXT_MUTED
)
from apps.reports.services.audit_service import ReportAuditService


class WorkInvoicePDFService:
    """
    Builds the official Work Entry / Commercial Invoice A4 PDF document.
    """

    @classmethod
    def generate_pdf(
        cls,
        entry_id: int,
        user=None
    ) -> HttpResponse:
        entry = MachineWorkEntry.objects.select_related(
            'machine', 'machine__machine_type', 'customer', 'operator', 'created_by'
        ).get(id=entry_id)

        customer = entry.customer
        machine = entry.machine
        styles = PDFReportBuilder.get_styles()
        elements = []
        usable_w = 523.0

        # 1. Company Letterhead
        as_of_str = PDFReportBuilder.format_date(entry.work_date)
        user_name = user.get_full_name() or user.username if user else "Billing Operator"

        letterhead = PDFReportBuilder.create_letterhead(
            report_title="AGRICULTURAL WORK INVOICE / BILL",
            period_str=None,
            as_of_str=as_of_str,
            generated_by_user=user_name,
            version="v1.0",
            usable_width=usable_w
        )
        elements.append(letterhead)
        elements.append(Spacer(1, 10))

        # 2. Invoice & Client Context Banner
        bill_no = entry.manual_bill_no or entry.work_code
        invoice_meta = Table([
            [
                [
                    Paragraph(f"INVOICE / BILL NO: <b>{bill_no}</b>", styles['BodyTextBold']),
                    Paragraph(f"Work Date: <b>{PDFReportBuilder.format_date(entry.work_date)}</b>", styles['BodyText']),
                    Paragraph(f"Payment Terms: <b>{entry.get_payment_mode_display()}</b>", styles['BodyText']),
                ],
                [
                    Paragraph("<b>BILLED TO (FARMER / CLIENT):</b>", styles['BodyTextBold']),
                    Paragraph(f"<b>{customer.name}</b> (Code: {customer.customer_code})", styles['BodyText']),
                    Paragraph(f"Village: {customer.location_address or 'Local Field'}", styles['BodyText']),
                    Paragraph(f"Phone: {customer.phone or '--'}", styles['BodyText']),
                ]
            ]
        ], colWidths=[usable_w * 0.45, usable_w * 0.55])
        invoice_meta.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), COLOR_BG_LIGHT),
            ('BOX', (0, 0), (-1, -1), 1, COLOR_BORDER),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('LEFTPADDING', (0, 0), (-1, -1), 8),
            ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ]))
        elements.append(invoice_meta)
        elements.append(Spacer(1, 10))

        # 3. Machine & Field Operational Specs
        operator_name = entry.operator.full_name if entry.operator else "Basaveshwara Harvesting Crew"
        meter_info = f"Start: {entry.start_meter or '--'} • End: {entry.end_meter or '--'} (Delta: {entry.meter_difference} {machine.get_meter_unit_display()})" if entry.meter_difference > 0 else "--"

        machine_specs = Table([
            [
                Paragraph("<b>EQUIPMENT &amp; FLEET SPECIFICATIONS</b>", styles['BodyTextBold']),
                Paragraph("<b>OPERATIONAL METRICS</b>", styles['BodyTextBold']),
            ],
            [
                Paragraph(f"Machine: <b>{machine.name}</b> ({machine.machine_type.name})", styles['BodyText']),
                Paragraph(f"Field Operator: <b>{operator_name}</b>", styles['BodyText']),
            ],
            [
                Paragraph(f"Reg / Machine Code: {machine.registration_no or machine.machine_code}", styles['BodyText']),
                Paragraph(f"Hour Meter Delta: {meter_info}", styles['BodyText']),
            ]
        ], colWidths=[usable_w * 0.50, usable_w * 0.50])
        machine_specs.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.white),
            ('BOX', (0, 0), (-1, -1), 0.5, COLOR_BORDER),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, COLOR_BG_ZEBRA),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
            ('LEFTPADDING', (0, 0), (-1, -1), 8),
            ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ]))
        elements.append(machine_specs)
        elements.append(Spacer(1, 12))

        # 4. Itemized Commercial Billing Table
        if entry.billing_type == MachineWorkEntry.BILLING_TIME_HOURLY:
            item_desc = (
                f"<b>Combine Harvester Field Harvesting Operation</b><br/>"
                f"Operating Timings: {entry.start_time or '--'} to {entry.end_time or '--'} "
                f"(Break Duration: {entry.break_hours} hrs)"
            )
            qty_str = f"{entry.net_working_hours} hrs"
            rate_str = PDFReportBuilder.format_inr(entry.hourly_rate)
        else:
            item_desc = f"<b>Tractor Agricultural Operation ({entry.get_billing_type_display()})</b>"
            qty_str = f"{entry.quantity} {entry.get_billing_type_display()}"
            rate_str = PDFReportBuilder.format_inr(entry.unit_rate)

        billing_table = Table([
            [
                Paragraph("<b>#</b>", styles['TableHeaderCenter']),
                Paragraph("<b>OPERATION &amp; SERVICE DESCRIPTION</b>", styles['TableHeader']),
                Paragraph("<b>USAGE / QUANTITY</b>", styles['TableHeaderCenter']),
                Paragraph("<b>UNIT RATE</b>", styles['TableHeaderRight']),
                Paragraph("<b>LINE TOTAL</b>", styles['TableHeaderRight']),
            ],
            [
                Paragraph("1", styles['TableCellCenter']),
                Paragraph(item_desc, styles['TableCell']),
                Paragraph(qty_str, styles['TableCellCenter']),
                Paragraph(rate_str, styles['TableCellRight']),
                Paragraph(PDFReportBuilder.format_inr(entry.total_amount), styles['TableCellRightBold']),
            ],
            [
                Paragraph("", styles['TableCell']),
                Paragraph("<b>GROSS BILL AMOUNT</b>", styles['TableCellBold']),
                Paragraph("", styles['TableCell']),
                Paragraph("", styles['TableCell']),
                Paragraph(f"<b>{PDFReportBuilder.format_inr(entry.total_amount)}</b>", styles['TableCellRightBold']),
            ],
            [
                Paragraph("", styles['TableCell']),
                Paragraph("<b>Less: Advance / Cash Paid on Field</b>", styles['TableCellBold']),
                Paragraph("", styles['TableCell']),
                Paragraph("", styles['TableCell']),
                Paragraph(f"-{PDFReportBuilder.format_inr(entry.advance_amount)}", styles['TableCellRightBold']),
            ],
            [
                Paragraph("", styles['TableCell']),
                Paragraph("<b>NET BALANCE DUE (ADDED TO FARMER UDHAR)</b>", styles['TableCellBold']),
                Paragraph("", styles['TableCell']),
                Paragraph("", styles['TableCell']),
                Paragraph(f"<b>{PDFReportBuilder.format_inr(entry.udhar_amount)}</b>", styles['TableCellRightBold']),
            ],
        ], colWidths=[usable_w * 0.06, usable_w * 0.48, usable_w * 0.16, usable_w * 0.14, usable_w * 0.16])

        billing_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), COLOR_HEADER_BG),
            ('BOX', (0, 0), (-1, -1), 1, COLOR_BORDER),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, COLOR_BORDER),
            ('BACKGROUND', (0, 1), (-1, 1), colors.white),
            ('BACKGROUND', (0, 2), (-1, 2), COLOR_BG_LIGHT),
            ('BACKGROUND', (0, 3), (-1, 3), COLOR_BG_LIGHT),
            ('BACKGROUND', (0, 4), (-1, 4), colors.HexColor('#FEE2E2')),  # Light rose for balance due
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ]))
        elements.append(billing_table)
        elements.append(Spacer(1, 15))

        # 5. Summary KPI Strip
        kpis = PDFReportBuilder.create_kpi_summary_box([
            ("GROSS WORK BILL", PDFReportBuilder.format_inr(entry.total_amount), COLOR_PRIMARY_DARK),
            ("ADVANCE COLLECTED", PDFReportBuilder.format_inr(entry.advance_amount), COLOR_EMERALD),
            ("BALANCE DUE (UDHAR)", PDFReportBuilder.format_inr(entry.udhar_amount), COLOR_ROSE),
        ], usable_width=usable_w)
        elements.append(kpis)
        elements.append(Spacer(1, 15))

        # 6. Authorization Block
        sig_block = PDFReportBuilder.create_signature_block(usable_width=usable_w, signatory_title="Authorized Representative")
        elements.append(KeepTogether([sig_block]))

        # 7. Audit Logging
        filename = f"work_invoice_{bill_no}_{timezone.now().strftime('%Y%m%d')}.pdf"
        ReportAuditService.log_report_generation(
            report_type=ReportAuditService.TYPE_WORK_INVOICE,
            user=user,
            related_object_id=entry.id,
            as_of_date=entry.work_date,
            file_name=filename,
            metadata={'work_code': entry.work_code, 'bill_no': bill_no, 'customer': customer.name, 'amount': str(entry.total_amount)}
        )

        return PDFReportBuilder.build_pdf_response(elements, filename=filename, orientation='portrait')
