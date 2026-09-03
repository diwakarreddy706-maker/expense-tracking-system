"""
Farmer Outstanding & Receivables Aging PDF Generator.
Audits unpaid farmer Udhar balances, aging buckets (0-30d, 31-60d, 61-90d, 91-180d, 181+d), and collection priorities.
Strictly read-only; consumes authoritative Customer, Receivable, and CustomerPayment records.
"""

from decimal import Decimal
from datetime import date
from typing import Optional, List, Dict, Any
from django.db.models import Sum, F, Min, Max
from django.utils import timezone
from django.http import HttpResponse

from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import (
    Paragraph, Table, TableStyle, Spacer, KeepTogether
)

from apps.finance.models import Customer, Receivable, CustomerPayment
from apps.reports.services.pdf_service import (
    PDFReportBuilder, COLOR_HEADER_BG, COLOR_BG_LIGHT, COLOR_BG_ZEBRA,
    COLOR_BORDER, COLOR_EMERALD, COLOR_ROSE, COLOR_AMBER, COLOR_PRIMARY_DARK, COLOR_TEXT_MUTED
)
from apps.reports.services.audit_service import ReportAuditService


class ReceivablesAgingPDFService:
    """
    Builds the official Farmer Receivables & Aging Analysis Landscape A4 PDF document.
    """

    @classmethod
    def get_receivables_aging_data(cls, as_of_date: Optional[date] = None) -> Dict[str, Any]:
        """Calculates aging buckets and outstanding amounts per farmer."""
        today = as_of_date or timezone.now().date()
        zero = Decimal('0.00')

        customers = Customer.objects.filter(is_deleted=False).prefetch_related('receivables', 'receivables__payments')

        farmer_rows = []
        fleet_total_billed = zero
        fleet_total_received = zero
        fleet_total_outstanding = zero

        bucket_totals = {
            '0_30': zero,
            '31_60': zero,
            '61_90': zero,
            '91_180': zero,
            '181_plus': zero,
        }

        for c in customers:
            unpaid_recs = c.receivables.filter(is_deleted=False).exclude(status=Receivable.STATUS_PAID)
            all_recs = c.receivables.filter(is_deleted=False)

            total_billed = all_recs.aggregate(s=Sum('total_amount'))['s'] or zero
            total_received = all_recs.aggregate(s=Sum('received_amount'))['s'] or zero
            outstanding = (total_billed - total_received).quantize(Decimal('0.01'))

            if outstanding <= zero:
                continue  # Only show farmers with active debt for collection

            oldest_date = unpaid_recs.aggregate(m=Min('bill_date'))['m']
            days_old = (today - oldest_date).days if oldest_date else 0

            # Bucket classification
            if days_old <= 30:
                bucket_name = "0–30 Days"
                bucket_totals['0_30'] += outstanding
            elif days_old <= 60:
                bucket_name = "31–60 Days"
                bucket_totals['31_60'] += outstanding
            elif days_old <= 90:
                bucket_name = "61–90 Days"
                bucket_totals['61_90'] += outstanding
            elif days_old <= 180:
                bucket_name = "91–180 Days"
                bucket_totals['91_180'] += outstanding
            else:
                bucket_name = "181+ Days"
                bucket_totals['181_plus'] += outstanding

            # Last payment date
            last_payment = CustomerPayment.objects.filter(
                receivable__customer=c,
                receivable__is_deleted=False
            ).aggregate(m=Max('payment_date'))['m']

            farmer_rows.append({
                'customer': c,
                'total_billed': total_billed,
                'total_received': total_received,
                'outstanding': outstanding,
                'oldest_date': oldest_date,
                'days_old': days_old,
                'bucket_name': bucket_name,
                'last_payment_date': last_payment,
            })

            fleet_total_billed += total_billed
            fleet_total_received += total_received
            fleet_total_outstanding += outstanding

        # Sort by highest outstanding amount descending
        farmer_rows.sort(key=lambda x: x['outstanding'], reverse=True)

        return {
            'as_of_date': today,
            'rows': farmer_rows,
            'total_billed': fleet_total_billed,
            'total_received': fleet_total_received,
            'total_outstanding': fleet_total_outstanding,
            'bucket_totals': bucket_totals,
            'active_debtors_count': len(farmer_rows),
        }

    @classmethod
    def generate_pdf(
        cls,
        user=None,
        as_of_date: Optional[date] = None
    ) -> HttpResponse:
        styles = PDFReportBuilder.get_styles()
        elements = []
        usable_w = 769.0  # Landscape A4 (842) - 2 * 36pt margins

        # 1. Company Letterhead
        today = as_of_date or timezone.now().date()
        as_of_str = PDFReportBuilder.format_date(today)
        user_name = user.get_full_name() or user.username if user else "Credit Controller"

        letterhead = PDFReportBuilder.create_letterhead(
            report_title="FARMER OUTSTANDING & RECEIVABLES AGING REPORT",
            period_str=None,
            as_of_str=as_of_str,
            generated_by_user=user_name,
            version="v1.0",
            usable_width=usable_w
        )
        elements.append(letterhead)
        elements.append(Spacer(1, 10))

        # 2. Get Receivables Aging Data
        data = cls.get_receivables_aging_data(as_of_date=today)
        buckets = data['bucket_totals']

        # 3. Aging Bucket Strip
        kpi_box = PDFReportBuilder.create_kpi_summary_box([
            ("TOTAL UDHAR DUE", PDFReportBuilder.format_inr(data['total_outstanding']), COLOR_ROSE),
            ("0–30 DAYS (CURRENT)", PDFReportBuilder.format_inr(buckets['0_30']), COLOR_EMERALD),
            ("31–60 DAYS", PDFReportBuilder.format_inr(buckets['31_60']), COLOR_AMBER),
            ("61–90 DAYS", PDFReportBuilder.format_inr(buckets['61_90']), COLOR_AMBER),
            ("91–180 DAYS", PDFReportBuilder.format_inr(buckets['91_180']), COLOR_ROSE),
            ("181+ DAYS (CRITICAL)", PDFReportBuilder.format_inr(buckets['181_plus']), COLOR_ROSE),
        ], usable_width=usable_w)
        elements.append(kpi_box)
        elements.append(Spacer(1, 12))

        # 4. Detailed Aging Table
        table_rows = [
            [
                Paragraph("<b>FARMER NAME &amp; CODE</b>", styles['TableHeader']),
                Paragraph("<b>VILLAGE / LOCATION</b>", styles['TableHeader']),
                Paragraph("<b>PHONE</b>", styles['TableHeaderCenter']),
                Paragraph("<b>TOTAL BILLED</b>", styles['TableHeaderRight']),
                Paragraph("<b>TOTAL PAID</b>", styles['TableHeaderRight']),
                Paragraph("<b>OUTSTANDING DUE</b>", styles['TableHeaderRight']),
                Paragraph("<b>OLDEST BILL</b>", styles['TableHeaderCenter']),
                Paragraph("<b>AGING BUCKET</b>", styles['TableHeaderCenter']),
                Paragraph("<b>LAST PAYMENT</b>", styles['TableHeaderCenter']),
            ]
        ]

        for r in data['rows']:
            c = r['customer']
            aging_color = COLOR_EMERALD if r['days_old'] <= 30 else (COLOR_AMBER if r['days_old'] <= 90 else COLOR_ROSE)
            aging_style = ParagraphStyle(f'ag_{c.id}', parent=styles['TableCellCenter'], textColor=aging_color)

            table_rows.append([
                Paragraph(f"<b>{c.name}</b><br/><font size=6.5 color='#64748B'>{c.customer_code}</font>", styles['TableCell']),
                Paragraph(c.location_address or "Local Field", styles['TableCell']),
                Paragraph(c.phone or "--", styles['TableCellCenter']),
                Paragraph(PDFReportBuilder.format_inr(r['total_billed'], show_symbol=False), styles['TableCellRight']),
                Paragraph(PDFReportBuilder.format_inr(r['total_received'], show_symbol=False), styles['TableCellRight']),
                Paragraph(PDFReportBuilder.format_inr(r['outstanding'], show_symbol=False), styles['TableCellRightBold']),
                Paragraph(PDFReportBuilder.format_date(r['oldest_date']), styles['TableCellCenter']),
                Paragraph(f"<b>{r['bucket_name']}</b> ({r['days_old']}d)", aging_style),
                Paragraph(PDFReportBuilder.format_date(r['last_payment_date']), styles['TableCellCenter']),
            ])

        if not data['rows']:
            table_rows.append([
                Paragraph("NO_RECORDS", styles['TableCell']),
                Paragraph("All farmer accounts are settled with zero outstanding debt.", styles['TableCell']),
                Paragraph("--", styles['TableCellCenter']),
                Paragraph("--", styles['TableCellRight']),
                Paragraph("--", styles['TableCellRight']),
                Paragraph(PDFReportBuilder.format_inr(Decimal('0.00'), show_symbol=False), styles['TableCellRightBold']),
                Paragraph("--", styles['TableCellCenter']),
                Paragraph("0 Days", styles['TableCellCenter']),
                Paragraph("--", styles['TableCellCenter']),
            ])

        table_rows.append([
            Paragraph(f"<b>TOTAL RECEIVABLES ({data['active_debtors_count']} Farmers)</b>", styles['TableCellBold']),
            Paragraph("--", styles['TableCell']),
            Paragraph("--", styles['TableCellCenter']),
            Paragraph(f"<b>{PDFReportBuilder.format_inr(data['total_billed'], show_symbol=False)}</b>", styles['TableCellRightBold']),
            Paragraph(f"<b>{PDFReportBuilder.format_inr(data['total_received'], show_symbol=False)}</b>", styles['TableCellRightBold']),
            Paragraph(f"<b>{PDFReportBuilder.format_inr(data['total_outstanding'], show_symbol=False)}</b>", styles['TableCellRightBold']),
            Paragraph("--", styles['TableCellCenter']),
            Paragraph("--", styles['TableCellCenter']),
            Paragraph("--", styles['TableCellCenter']),
        ])

        # Widths: Sum = 769pt (Landscape A4)
        col_w = [140, 109, 80, 80, 80, 85, 65, 75, 55]
        aging_table = Table(table_rows, colWidths=col_w, repeatRows=1)

        t_style = [
            ('BACKGROUND', (0, 0), (-1, 0), COLOR_HEADER_BG),
            ('BOX', (0, 0), (-1, -1), 1, COLOR_BORDER),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, COLOR_BORDER),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('LEFTPADDING', (0, 0), (-1, -1), 3),
            ('RIGHTPADDING', (0, 0), (-1, -1), 3),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('BACKGROUND', (0, -1), (-1, -1), COLOR_BG_LIGHT),
        ]

        for i in range(1, len(table_rows) - 1):
            if i % 2 == 0:
                t_style.append(('BACKGROUND', (0, i), (-1, i), COLOR_BG_ZEBRA))
            else:
                t_style.append(('BACKGROUND', (0, i), (-1, i), colors.white))

        aging_table.setStyle(TableStyle(t_style))
        elements.append(aging_table)
        elements.append(Spacer(1, 15))

        # 5. Authorization Block
        sig_block = PDFReportBuilder.create_signature_block(usable_width=usable_w, signatory_title="Credit Controller & Managing Partner")
        elements.append(KeepTogether([sig_block]))

        # 6. Audit Logging
        filename = f"receivables_aging_{today.strftime('%Y%m%d')}.pdf"
        ReportAuditService.log_report_generation(
            report_type=ReportAuditService.TYPE_RECEIVABLES_AGING,
            user=user,
            as_of_date=today,
            file_name=filename,
            metadata={'total_outstanding': str(data['total_outstanding']), 'debtor_count': data['active_debtors_count']}
        )

        return PDFReportBuilder.build_pdf_response(elements, filename=filename, orientation='landscape')
