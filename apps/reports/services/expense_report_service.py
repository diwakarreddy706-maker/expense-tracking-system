"""
Comprehensive Expense Analysis PDF Generator.
Categorical, payment-method, and monthly breakdown of operational expenses.
Strictly read-only; consumes authoritative Expense, ExpenseCategory, and Account records.
"""

from decimal import Decimal
from typing import Optional, List, Dict, Any
from django.db.models import Sum, Count
from django.utils import timezone
from django.http import HttpResponse

from reportlab.lib import colors
from reportlab.platypus import (
    Paragraph, Table, TableStyle, Spacer, KeepTogether
)

from apps.expenses.models import Expense, ExpenseCategory
from apps.reports.services.pdf_service import (
    PDFReportBuilder, COLOR_HEADER_BG, COLOR_BG_LIGHT, COLOR_BG_ZEBRA,
    COLOR_BORDER, COLOR_EMERALD, COLOR_ROSE, COLOR_AMBER, COLOR_PRIMARY_DARK, COLOR_TEXT_MUTED
)
from apps.reports.services.audit_service import ReportAuditService


class ExpenseReportPDFService:
    """
    Builds the official Comprehensive Expense Analysis A4 PDF document.
    """

    @classmethod
    def get_expense_analysis_data(
        cls,
        start_date=None,
        end_date=None,
        category_id=None,
        machine_id=None,
        payment_method=None
    ) -> Dict[str, Any]:
        """Calculates categorical, payment-method, and monthly distributions."""
        zero = Decimal('0.00')
        qs = Expense.objects.filter(is_deleted=False, is_reversed=False).select_related(
            'category', 'account', 'machine', 'supplier'
        ).order_by('-expense_date', '-id')

        if start_date:
            qs = qs.filter(expense_date__gte=start_date)
        if end_date:
            qs = qs.filter(expense_date__lte=end_date)
        if category_id:
            qs = qs.filter(category_id=category_id)
        if machine_id:
            qs = qs.filter(machine_id=machine_id)
        if payment_method:
            qs = qs.filter(payment_method=payment_method)

        total_amount = qs.aggregate(s=Sum('amount'))['s'] or zero
        total_count = qs.count()

        # 1. Category Breakdown
        cat_group = (
            qs.values('category__name', 'category__code')
            .annotate(total=Sum('amount'), count=Count('id'))
            .order_by('-total')
        )
        cat_rows = []
        for c in cat_group:
            cat_tot = c['total'] or zero
            pct = ((cat_tot / total_amount) * Decimal('100.00')).quantize(Decimal('0.1')) if total_amount > zero else zero
            cat_rows.append({
                'name': c['category__name'] or 'Uncategorized',
                'code': c['category__code'] or '--',
                'total': cat_tot,
                'count': c['count'],
                'pct': pct,
            })

        # 2. Payment Method Breakdown
        method_group = (
            qs.values('payment_method')
            .annotate(total=Sum('amount'), count=Count('id'))
            .order_by('-total')
        )
        method_rows = []
        for m in method_group:
            m_tot = m['total'] or zero
            pct = ((m_tot / total_amount) * Decimal('100.00')).quantize(Decimal('0.1')) if total_amount > zero else zero
            method_rows.append({
                'method': m['payment_method'] or 'OTHER',
                'total': m_tot,
                'count': m['count'],
                'pct': pct,
            })

        return {
            'total_amount': total_amount,
            'total_count': total_count,
            'categories': cat_rows,
            'payment_methods': method_rows,
            'expenses': qs[:100],  # Recent sample items
        }

    @classmethod
    def generate_pdf(
        cls,
        user=None,
        start_date=None,
        end_date=None,
        category_id=None,
        machine_id=None,
        payment_method=None
    ) -> HttpResponse:
        styles = PDFReportBuilder.get_styles()
        elements = []
        usable_w = 523.0  # Portrait A4

        # 1. Company Letterhead
        period_str = f"{PDFReportBuilder.format_date(start_date)} to {PDFReportBuilder.format_date(end_date)}" if (start_date or end_date) else "Complete Financial History"
        as_of_str = PDFReportBuilder.format_date(timezone.now().date())
        user_name = user.get_full_name() or user.username if user else "Financial Controller"

        letterhead = PDFReportBuilder.create_letterhead(
            report_title="COMPREHENSIVE EXPENSE ANALYSIS STATEMENT",
            period_str=period_str,
            as_of_str=as_of_str,
            generated_by_user=user_name,
            version="v1.0",
            usable_width=usable_w
        )
        elements.append(letterhead)
        elements.append(Spacer(1, 10))

        # 2. Get Analysis Data
        data = cls.get_expense_analysis_data(
            start_date=start_date,
            end_date=end_date,
            category_id=category_id,
            machine_id=machine_id,
            payment_method=payment_method
        )

        # 3. Executive KPI Strip
        kpi_box = PDFReportBuilder.create_kpi_summary_box([
            ("TOTAL EXPENSES", PDFReportBuilder.format_inr(data['total_amount']), COLOR_ROSE),
            ("TRANSACTION COUNT", f"{data['total_count']} Entries", COLOR_PRIMARY_DARK),
            ("EXPENSE CATEGORIES", f"{len(data['categories'])} Types", COLOR_AMBER),
        ], usable_width=usable_w)
        elements.append(kpi_box)
        elements.append(Spacer(1, 12))

        # 4. Category Breakdown Table
        elements.append(Paragraph("<b>1. EXPENSE CATEGORY DISTRIBUTION</b>", styles['SectionTitle']))
        cat_table_rows = [
            [
                Paragraph("<b>CATEGORY NAME</b>", styles['TableHeader']),
                Paragraph("<b>CODE</b>", styles['TableHeaderCenter']),
                Paragraph("<b>TRANSACTIONS</b>", styles['TableHeaderCenter']),
                Paragraph("<b>TOTAL EXPENDITURE</b>", styles['TableHeaderRight']),
                Paragraph("<b>SHARE %</b>", styles['TableHeaderCenter']),
            ]
        ]

        for c in data['categories']:
            cat_table_rows.append([
                Paragraph(c['name'], styles['TableCellBold']),
                Paragraph(c['code'], styles['TableCellCenter']),
                Paragraph(str(c['count']), styles['TableCellCenter']),
                Paragraph(PDFReportBuilder.format_inr(c['total'], show_symbol=False), styles['TableCellRight']),
                Paragraph(f"{c['pct']}%", styles['TableCellCenter']),
            ])

        if not data['categories']:
            cat_table_rows.append([
                Paragraph("NO_RECORDS", styles['TableCell']),
                Paragraph("--", styles['TableCellCenter']),
                Paragraph("--", styles['TableCellCenter']),
                Paragraph(PDFReportBuilder.format_inr(Decimal('0.00'), show_symbol=False), styles['TableCellRight']),
                Paragraph("0.0%", styles['TableCellCenter']),
            ])

        cat_table_rows.append([
            Paragraph("<b>TOTALS</b>", styles['TableCellBold']),
            Paragraph("--", styles['TableCellCenter']),
            Paragraph(f"<b>{data['total_count']}</b>", styles['TableCellCenter']),
            Paragraph(f"<b>{PDFReportBuilder.format_inr(data['total_amount'], show_symbol=False)}</b>", styles['TableCellRightBold']),
            Paragraph("<b>100.0%</b>", styles['TableCellCenter']),
        ])

        col_w_cat = [183, 70, 80, 120, 70]
        cat_table = Table(cat_table_rows, colWidths=col_w_cat, repeatRows=1)
        t_style_cat = [
            ('BACKGROUND', (0, 0), (-1, 0), COLOR_HEADER_BG),
            ('BOX', (0, 0), (-1, -1), 1, COLOR_BORDER),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, COLOR_BORDER),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('LEFTPADDING', (0, 0), (-1, -1), 4),
            ('RIGHTPADDING', (0, 0), (-1, -1), 4),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('BACKGROUND', (0, -1), (-1, -1), COLOR_BG_LIGHT),
        ]
        for i in range(1, len(cat_table_rows) - 1):
            if i % 2 == 0:
                t_style_cat.append(('BACKGROUND', (0, i), (-1, i), COLOR_BG_ZEBRA))
            else:
                t_style_cat.append(('BACKGROUND', (0, i), (-1, i), colors.white))

        cat_table.setStyle(TableStyle(t_style_cat))
        elements.append(cat_table)
        elements.append(Spacer(1, 12))

        # 5. Payment Method Breakdown Table
        elements.append(Paragraph("<b>2. PAYMENT METHOD UTILIZATION</b>", styles['SectionTitle']))
        pm_table_rows = [
            [
                Paragraph("<b>PAYMENT METHOD / CHANNEL</b>", styles['TableHeader']),
                Paragraph("<b>TRANSACTIONS</b>", styles['TableHeaderCenter']),
                Paragraph("<b>AMOUNT DISBURSED</b>", styles['TableHeaderRight']),
                Paragraph("<b>SHARE %</b>", styles['TableHeaderCenter']),
            ]
        ]

        for p in data['payment_methods']:
            pm_table_rows.append([
                Paragraph(p['method'].replace('_', ' ').title(), styles['TableCellBold']),
                Paragraph(str(p['count']), styles['TableCellCenter']),
                Paragraph(PDFReportBuilder.format_inr(p['total'], show_symbol=False), styles['TableCellRight']),
                Paragraph(f"{p['pct']}%", styles['TableCellCenter']),
            ])

        col_w_pm = [223, 90, 130, 80]
        pm_table = Table(pm_table_rows, colWidths=col_w_pm, repeatRows=1)
        t_style_pm = [
            ('BACKGROUND', (0, 0), (-1, 0), COLOR_HEADER_BG),
            ('BOX', (0, 0), (-1, -1), 1, COLOR_BORDER),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, COLOR_BORDER),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('LEFTPADDING', (0, 0), (-1, -1), 4),
            ('RIGHTPADDING', (0, 0), (-1, -1), 4),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]
        for i in range(1, len(pm_table_rows)):
            if i % 2 == 0:
                t_style_pm.append(('BACKGROUND', (0, i), (-1, i), COLOR_BG_ZEBRA))
            else:
                t_style_pm.append(('BACKGROUND', (0, i), (-1, i), colors.white))

        pm_table.setStyle(TableStyle(t_style_pm))
        elements.append(pm_table)
        elements.append(Spacer(1, 15))

        # 6. Authorization Block
        sig_block = PDFReportBuilder.create_signature_block(usable_width=usable_w, signatory_title="Chief Accountant")
        elements.append(KeepTogether([sig_block]))

        # 7. Audit Logging
        filename = f"expense_analysis_{timezone.now().strftime('%Y%m%d')}.pdf"
        ReportAuditService.log_report_generation(
            report_type=ReportAuditService.TYPE_EXPENSE_ANALYSIS,
            user=user,
            period_start=start_date,
            period_end=end_date,
            file_name=filename,
            metadata={'total_expenses': str(data['total_amount']), 'count': data['total_count']}
        )

        return PDFReportBuilder.build_pdf_response(elements, filename=filename, orientation='portrait')
