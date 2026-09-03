"""
Machinery Operational Profit & Loss (P&L) PDF Generator.
Calculates revenue, fuel, maintenance, operator wages, and net profit per equipment.
Strictly read-only; consumes authoritative Machine, MachineWorkEntry, Expense, and FuelEntry records.
"""

from decimal import Decimal
from typing import Optional, List, Dict, Any
from django.db.models import Sum, Q
from django.utils import timezone
from django.http import HttpResponse

from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import (
    Paragraph, Table, TableStyle, Spacer, KeepTogether, PageBreak
)

from apps.machines.models import Machine, MachineWorkEntry
from apps.expenses.models import Expense
from apps.fuel.models import FuelEntry
from apps.reports.services.pdf_service import (
    PDFReportBuilder, COLOR_HEADER_BG, COLOR_BG_LIGHT, COLOR_BG_ZEBRA,
    COLOR_BORDER, COLOR_EMERALD, COLOR_ROSE, COLOR_AMBER, COLOR_PRIMARY_DARK, COLOR_TEXT_MUTED
)
from apps.reports.services.audit_service import ReportAuditService


class MachineryPnLPDFService:
    """
    Builds the official Machinery Operational P&L Landscape A4 PDF document.
    """

    @classmethod
    def get_machinery_pnl_data(
        cls,
        start_date=None,
        end_date=None,
        machine_id=None
    ) -> Dict[str, Any]:
        """
        Calculates authoritative machine-wise revenue, costs, and operational metrics.
        Cost Attribution:
        - Revenue: MachineWorkEntry.total_amount for each machine
        - Fuel Cost: Machine-specific fuel expenses (avoids double counting)
        - Maintenance & Parts: Machine-specific repair & spare parts expenses
        - Wages: Machine-specific operator wages & payouts
        """
        zero = Decimal('0.00')
        machines_qs = Machine.objects.filter(is_deleted=False).select_related('machine_type', 'rented_owner')
        if machine_id:
            machines_qs = machines_qs.filter(id=machine_id)

        rows = []
        fleet_total_revenue = zero
        fleet_total_fuel_cost = zero
        fleet_total_maintenance = zero
        fleet_total_wages = zero
        fleet_total_other_costs = zero
        fleet_total_costs = zero
        fleet_total_net_profit = zero
        fleet_total_hours = zero
        fleet_total_acres = zero
        fleet_total_fuel_liters = zero

        for m in machines_qs:
            # 1. Revenue
            work_qs = MachineWorkEntry.objects.filter(machine=m, is_deleted=False)
            if start_date:
                work_qs = work_qs.filter(work_date__gte=start_date)
            if end_date:
                work_qs = work_qs.filter(work_date__lte=end_date)

            revenue = work_qs.aggregate(s=Sum('total_amount'))['s'] or zero
            hours = work_qs.filter(
                billing_type=MachineWorkEntry.BILLING_TIME_HOURLY
            ).aggregate(s=Sum('net_working_hours'))['s'] or zero
            acres = work_qs.filter(
                billing_type=MachineWorkEntry.BILLING_ACRE
            ).aggregate(s=Sum('quantity'))['s'] or zero

            # 2. Fuel Liters
            fuel_entry_qs = FuelEntry.objects.filter(machine=m, is_deleted=False, linked_expense__is_reversed=False)
            if start_date:
                fuel_entry_qs = fuel_entry_qs.filter(date__gte=start_date)
            if end_date:
                fuel_entry_qs = fuel_entry_qs.filter(date__lte=end_date)
            fuel_liters = fuel_entry_qs.aggregate(s=Sum('quantity'))['s'] or zero

            # 3. Direct Costs from Machine-Attributed Expenses
            exp_qs = Expense.objects.filter(machine=m, is_deleted=False, is_reversed=False)
            if start_date:
                exp_qs = exp_qs.filter(expense_date__gte=start_date)
            if end_date:
                exp_qs = exp_qs.filter(expense_date__lte=end_date)

            fuel_cost = exp_qs.filter(
                Q(category__name__icontains='fuel') | Q(category__name__icontains='diesel') | Q(category__code__icontains='fuel')
            ).aggregate(s=Sum('amount'))['s'] or zero

            maint_cost = exp_qs.filter(
                Q(category__name__icontains='repair') | Q(category__name__icontains='service') | Q(category__name__icontains='maintenance') | Q(category__code__icontains='maint')
            ).aggregate(s=Sum('amount'))['s'] or zero

            parts_cost = exp_qs.filter(
                Q(category__name__icontains='spare') | Q(category__name__icontains='part') | Q(category__code__icontains='spare')
            ).aggregate(s=Sum('amount'))['s'] or zero

            wage_cost = exp_qs.filter(
                Q(category__name__icontains='wage') | Q(category__name__icontains='salary') | Q(category__name__icontains='operator') | Q(category__code__icontains='wage')
            ).aggregate(s=Sum('amount'))['s'] or zero

            # Other costs attributed to this machine
            other_cost = exp_qs.exclude(
                Q(category__name__icontains='fuel') | Q(category__name__icontains='diesel') | Q(category__code__icontains='fuel') |
                Q(category__name__icontains='repair') | Q(category__name__icontains='service') | Q(category__name__icontains='maintenance') | Q(category__code__icontains='maint') |
                Q(category__name__icontains='spare') | Q(category__name__icontains='part') | Q(category__code__icontains='spare') |
                Q(category__name__icontains='wage') | Q(category__name__icontains='salary') | Q(category__name__icontains='operator') | Q(category__code__icontains='wage')
            ).aggregate(s=Sum('amount'))['s'] or zero

            total_maint_parts = (maint_cost + parts_cost).quantize(Decimal('0.01'))
            total_cost = (fuel_cost + total_maint_parts + wage_cost + other_cost).quantize(Decimal('0.01'))
            net_profit = (revenue - total_cost).quantize(Decimal('0.01'))
            margin_pct = ((net_profit / revenue) * Decimal('100.00')).quantize(Decimal('0.1')) if revenue > zero else zero

            rev_per_hour = (revenue / hours).quantize(Decimal('0.01')) if hours > zero else zero
            fuel_cost_per_hour = (fuel_cost / hours).quantize(Decimal('0.01')) if hours > zero else zero

            rows.append({
                'machine': m,
                'revenue': revenue,
                'fuel_cost': fuel_cost,
                'fuel_liters': fuel_liters,
                'maintenance_cost': total_maint_parts,
                'wage_cost': wage_cost,
                'other_cost': other_cost,
                'total_cost': total_cost,
                'net_profit': net_profit,
                'margin_pct': margin_pct,
                'hours': hours,
                'acres': acres,
                'rev_per_hour': rev_per_hour,
                'fuel_cost_per_hour': fuel_cost_per_hour,
            })

            fleet_total_revenue += revenue
            fleet_total_fuel_cost += fuel_cost
            fleet_total_maintenance += total_maint_parts
            fleet_total_wages += wage_cost
            fleet_total_other_costs += other_cost
            fleet_total_costs += total_cost
            fleet_total_net_profit += net_profit
            fleet_total_hours += hours
            fleet_total_acres += acres
            fleet_total_fuel_liters += fuel_liters

        fleet_margin_pct = ((fleet_total_net_profit / fleet_total_revenue) * Decimal('100.00')).quantize(Decimal('0.1')) if fleet_total_revenue > zero else zero

        return {
            'rows': rows,
            'totals': {
                'revenue': fleet_total_revenue,
                'fuel_cost': fleet_total_fuel_cost,
                'maintenance_cost': fleet_total_maintenance,
                'wage_cost': fleet_total_wages,
                'other_cost': fleet_total_other_costs,
                'total_cost': fleet_total_costs,
                'net_profit': fleet_total_net_profit,
                'margin_pct': fleet_margin_pct,
                'hours': fleet_total_hours,
                'acres': fleet_total_acres,
                'fuel_liters': fleet_total_fuel_liters,
            }
        }

    @classmethod
    def generate_pdf(
        cls,
        user=None,
        start_date=None,
        end_date=None,
        machine_id=None
    ) -> HttpResponse:
        styles = PDFReportBuilder.get_styles()
        elements = []
        usable_w = 769.0  # Landscape A4 (842) - 2 * 36pt margins

        # 1. Company Letterhead
        period_str = f"{PDFReportBuilder.format_date(start_date)} to {PDFReportBuilder.format_date(end_date)}" if (start_date or end_date) else "All-Time Fleet History"
        as_of_str = PDFReportBuilder.format_date(timezone.now().date())
        user_name = user.get_full_name() or user.username if user else "Financial Auditor"

        letterhead = PDFReportBuilder.create_letterhead(
            report_title="MACHINERY OPERATIONAL PROFIT & LOSS (P&L) STATEMENT",
            period_str=period_str,
            as_of_str=as_of_str,
            generated_by_user=user_name,
            version="v1.0",
            usable_width=usable_w
        )
        elements.append(letterhead)
        elements.append(Spacer(1, 10))

        # 2. Get Authoritative P&L Dataset
        pnl_data = cls.get_machinery_pnl_data(start_date=start_date, end_date=end_date, machine_id=machine_id)
        totals = pnl_data['totals']

        # 3. Fleet Executive KPIs
        kpi_box = PDFReportBuilder.create_kpi_summary_box([
            ("FLEET REVENUE", PDFReportBuilder.format_inr(totals['revenue']), COLOR_PRIMARY_DARK),
            ("TOTAL DIESEL COST", PDFReportBuilder.format_inr(totals['fuel_cost']), COLOR_ROSE),
            ("MAINTENANCE & PARTS", PDFReportBuilder.format_inr(totals['maintenance_cost']), COLOR_AMBER),
            ("OPERATOR WAGES", PDFReportBuilder.format_inr(totals['wage_cost']), COLOR_AMBER),
            ("TOTAL DIRECT COSTS", PDFReportBuilder.format_inr(totals['total_cost']), COLOR_ROSE),
            ("NET FLEET PROFIT", PDFReportBuilder.format_inr(totals['net_profit']), COLOR_EMERALD),
            ("NET MARGIN %", f"{totals['margin_pct']}%", COLOR_EMERALD if totals['net_profit'] >= 0 else COLOR_ROSE),
        ], usable_width=usable_w)
        elements.append(kpi_box)
        elements.append(Spacer(1, 12))

        # 4. Machine-by-Machine Detailed Breakdown Table
        table_rows = [
            [
                Paragraph("<b>MACHINE &amp; FLEET SPEC</b>", styles['TableHeader']),
                Paragraph("<b>HOURS / ACRES</b>", styles['TableHeaderCenter']),
                Paragraph("<b>DIESEL (L)</b>", styles['TableHeaderCenter']),
                Paragraph("<b>GROSS REVENUE</b>", styles['TableHeaderRight']),
                Paragraph("<b>DIESEL COST</b>", styles['TableHeaderRight']),
                Paragraph("<b>MAINT &amp; PARTS</b>", styles['TableHeaderRight']),
                Paragraph("<b>WAGES &amp; CREW</b>", styles['TableHeaderRight']),
                Paragraph("<b>TOTAL COST</b>", styles['TableHeaderRight']),
                Paragraph("<b>NET PROFIT</b>", styles['TableHeaderRight']),
                Paragraph("<b>MARGIN</b>", styles['TableHeaderCenter']),
            ]
        ]

        for r in pnl_data['rows']:
            m = r['machine']
            usage_str = f"{r['hours']}h • {r['acres']}ac"
            profit_color = COLOR_EMERALD if r['net_profit'] >= 0 else COLOR_ROSE
            profit_style = ParagraphStyle(f'prof_{m.id}', parent=styles['TableCellRightBold'], textColor=profit_color)
            margin_style = ParagraphStyle(f'marg_{m.id}', parent=styles['TableCellCenter'], textColor=profit_color)

            table_rows.append([
                Paragraph(f"<b>{m.name}</b><br/><font size=6.5 color='#64748B'>{m.machine_code} • {m.machine_type.name}</font>", styles['TableCell']),
                Paragraph(usage_str, styles['TableCellCenter']),
                Paragraph(f"{r['fuel_liters']} L", styles['TableCellCenter']),
                Paragraph(PDFReportBuilder.format_inr(r['revenue'], show_symbol=False), styles['TableCellRight']),
                Paragraph(PDFReportBuilder.format_inr(r['fuel_cost'], show_symbol=False), styles['TableCellRight']),
                Paragraph(PDFReportBuilder.format_inr(r['maintenance_cost'], show_symbol=False), styles['TableCellRight']),
                Paragraph(PDFReportBuilder.format_inr(r['wage_cost'], show_symbol=False), styles['TableCellRight']),
                Paragraph(PDFReportBuilder.format_inr(r['total_cost'], show_symbol=False), styles['TableCellRight']),
                Paragraph(PDFReportBuilder.format_inr(r['net_profit'], show_symbol=False), profit_style),
                Paragraph(f"{r['margin_pct']}%", margin_style),
            ])

        if not pnl_data['rows']:
            table_rows.append([
                Paragraph("NO_RECORDS", styles['TableCell']),
                Paragraph("--", styles['TableCellCenter']),
                Paragraph("--", styles['TableCellCenter']),
                Paragraph("--", styles['TableCellRight']),
                Paragraph("--", styles['TableCellRight']),
                Paragraph("--", styles['TableCellRight']),
                Paragraph("--", styles['TableCellRight']),
                Paragraph("--", styles['TableCellRight']),
                Paragraph(PDFReportBuilder.format_inr(Decimal('0.00'), show_symbol=False), styles['TableCellRightBold']),
                Paragraph("0.0%", styles['TableCellCenter']),
            ])

        # Summary Row
        table_rows.append([
            Paragraph("<b>FLEET TOTALS</b>", styles['TableCellBold']),
            Paragraph(f"<b>{totals['hours']}h • {totals['acres']}ac</b>", styles['TableCellCenter']),
            Paragraph(f"<b>{totals['fuel_liters']} L</b>", styles['TableCellCenter']),
            Paragraph(f"<b>{PDFReportBuilder.format_inr(totals['revenue'], show_symbol=False)}</b>", styles['TableCellRightBold']),
            Paragraph(f"<b>{PDFReportBuilder.format_inr(totals['fuel_cost'], show_symbol=False)}</b>", styles['TableCellRightBold']),
            Paragraph(f"<b>{PDFReportBuilder.format_inr(totals['maintenance_cost'], show_symbol=False)}</b>", styles['TableCellRightBold']),
            Paragraph(f"<b>{PDFReportBuilder.format_inr(totals['wage_cost'], show_symbol=False)}</b>", styles['TableCellRightBold']),
            Paragraph(f"<b>{PDFReportBuilder.format_inr(totals['total_cost'], show_symbol=False)}</b>", styles['TableCellRightBold']),
            Paragraph(f"<b>{PDFReportBuilder.format_inr(totals['net_profit'], show_symbol=False)}</b>", styles['TableCellRightBold']),
            Paragraph(f"<b>{totals['margin_pct']}%</b>", styles['TableCellCenter']),
        ])

        # Column widths: Sum = 769pt (Landscape A4)
        col_w = [145, 68, 56, 75, 70, 75, 70, 75, 75, 60]
        pnl_table = Table(table_rows, colWidths=col_w, repeatRows=1)

        t_style = [
            ('BACKGROUND', (0, 0), (-1, 0), COLOR_HEADER_BG),
            ('BOX', (0, 0), (-1, -1), 1, COLOR_BORDER),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, COLOR_BORDER),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('LEFTPADDING', (0, 0), (-1, -1), 3),
            ('RIGHTPADDING', (0, 0), (-1, -1), 3),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('BACKGROUND', (0, -1), (-1, -1), COLOR_BG_LIGHT),  # Highlight totals row
        ]

        # Zebra striping
        for i in range(1, len(table_rows) - 1):
            if i % 2 == 0:
                t_style.append(('BACKGROUND', (0, i), (-1, i), COLOR_BG_ZEBRA))
            else:
                t_style.append(('BACKGROUND', (0, i), (-1, i), colors.white))

        pnl_table.setStyle(TableStyle(t_style))
        elements.append(pnl_table)
        elements.append(Spacer(1, 15))

        # 5. Authorization Block
        sig_block = PDFReportBuilder.create_signature_block(usable_width=usable_w, signatory_title="Operations & Accounts Manager")
        elements.append(KeepTogether([sig_block]))

        # 6. Audit Logging
        filename = f"machinery_pnl_{timezone.now().strftime('%Y%m%d')}.pdf"
        ReportAuditService.log_report_generation(
            report_type=ReportAuditService.TYPE_MACHINERY_PNL,
            user=user,
            period_start=start_date,
            period_end=end_date,
            file_name=filename,
            metadata={'machine_count': len(pnl_data['rows']), 'net_profit': str(totals['net_profit'])}
        )

        return PDFReportBuilder.build_pdf_response(elements, filename=filename, orientation='landscape')
