"""
Enterprise A4 PDF Generation Engine using ReportLab Platypus.
Provides reusable A4 page geometry, NumberedCanvas (Page X of Y), corporate typography,
company letterheads, repeated table headers, and deterministic financial formatting.
"""

import io
from decimal import Decimal
from typing import List, Dict, Any, Optional, Tuple
from django.utils import timezone
from django.http import HttpResponse

from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Table, TableStyle,
    Spacer, PageBreak, KeepTogether, HRFlowable
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY
from reportlab.pdfgen import canvas

from apps.reports.services.company_profile_service import CompanyProfileService


# Corporate Color Palette
COLOR_PRIMARY_DARK = colors.HexColor('#0F172A')   # Deep Slate
COLOR_HEADER_BG = colors.HexColor('#1E293B')      # Slate 800
COLOR_EMERALD = colors.HexColor('#059669')        # Emerald 600
COLOR_EMERALD_DARK = colors.HexColor('#064E3B')   # Emerald 900
COLOR_ROSE = colors.HexColor('#E11D48')           # Rose 600
COLOR_AMBER = colors.HexColor('#D97706')          # Amber 600
COLOR_CYAN = colors.HexColor('#0891B2')           # Cyan 600
COLOR_TEXT_MAIN = colors.HexColor('#1E293B')      # Slate 800
COLOR_TEXT_MUTED = colors.HexColor('#64748B')     # Slate 500
COLOR_BORDER = colors.HexColor('#CBD5E1')         # Slate 300
COLOR_BG_LIGHT = colors.HexColor('#F8FAFC')       # Slate 50
COLOR_BG_ZEBRA = colors.HexColor('#F1F5F9')       # Slate 100


class NumberedCanvas(canvas.Canvas):
    """
    Two-pass canvas for deterministic total page numbering ('Page X of Y')
    and running headers/footers across multi-page A4 documents.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_page_decorations(self, page_count: int):
        self.saveState()
        self.setFont("Helvetica", 7.5)
        self.setFillColor(COLOR_TEXT_MUTED)

        # Page Dimensions
        page_w, page_h = self._pagesize

        # Running Footer
        footer_y = 20
        self.setStrokeColor(COLOR_BORDER)
        self.setLineWidth(0.5)
        self.line(36, footer_y + 12, page_w - 36, footer_y + 12)

        # Left: Legal & System Notice
        self.drawString(36, footer_y, "AgriBOS ERP • Official Financial Record • Confidential & Authoritative")

        # Right: Page X of Y
        page_str = f"Page {self._pageNumber} of {page_count}"
        self.drawRightString(page_w - 36, footer_y, page_str)

        self.restoreState()


class PDFReportBuilder:
    """
    Core builder providing consistent corporate styling, letterheads,
    financial tables, and metadata for all PDF reports and vouchers.
    """

    @classmethod
    def get_styles(cls) -> Dict[str, ParagraphStyle]:
        """Returns standard corporate paragraph styles hierarchy."""
        base_styles = getSampleStyleSheet()
        styles = {}

        styles['CompanyName'] = ParagraphStyle(
            'CompanyName',
            parent=base_styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=13,
            leading=16,
            textColor=COLOR_PRIMARY_DARK,
        )

        styles['CompanyLegal'] = ParagraphStyle(
            'CompanyLegal',
            parent=base_styles['Normal'],
            fontName='Helvetica',
            fontSize=7.5,
            leading=10,
            textColor=COLOR_TEXT_MUTED,
        )

        styles['ReportTitle'] = ParagraphStyle(
            'ReportTitle',
            parent=base_styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=12,
            leading=15,
            textColor=COLOR_PRIMARY_DARK,
            alignment=TA_RIGHT,
        )

        styles['MetaLabel'] = ParagraphStyle(
            'MetaLabel',
            parent=base_styles['Normal'],
            fontName='Helvetica',
            fontSize=7.5,
            leading=10,
            textColor=COLOR_TEXT_MUTED,
            alignment=TA_RIGHT,
        )

        styles['MetaValue'] = ParagraphStyle(
            'MetaValue',
            parent=base_styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=7.5,
            leading=10,
            textColor=COLOR_PRIMARY_DARK,
            alignment=TA_RIGHT,
        )

        styles['SectionTitle'] = ParagraphStyle(
            'SectionTitle',
            parent=base_styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=10,
            leading=13,
            textColor=COLOR_PRIMARY_DARK,
            spaceBefore=8,
            spaceAfter=4,
        )

        styles['BodyText'] = ParagraphStyle(
            'BodyText',
            parent=base_styles['Normal'],
            fontName='Helvetica',
            fontSize=8,
            leading=11,
            textColor=COLOR_TEXT_MAIN,
        )

        styles['BodyTextBold'] = ParagraphStyle(
            'BodyTextBold',
            parent=base_styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=8,
            leading=11,
            textColor=COLOR_TEXT_MAIN,
        )

        styles['TableHeader'] = ParagraphStyle(
            'TableHeader',
            parent=base_styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=7.5,
            leading=9.5,
            textColor=colors.white,
            alignment=TA_LEFT,
        )

        styles['TableHeaderRight'] = ParagraphStyle(
            'TableHeaderRight',
            parent=base_styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=7.5,
            leading=9.5,
            textColor=colors.white,
            alignment=TA_RIGHT,
        )

        styles['TableHeaderCenter'] = ParagraphStyle(
            'TableHeaderCenter',
            parent=base_styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=7.5,
            leading=9.5,
            textColor=colors.white,
            alignment=TA_CENTER,
        )

        styles['TableCell'] = ParagraphStyle(
            'TableCell',
            parent=base_styles['Normal'],
            fontName='Helvetica',
            fontSize=7.5,
            leading=9.5,
            textColor=COLOR_TEXT_MAIN,
            alignment=TA_LEFT,
        )

        styles['TableCellBold'] = ParagraphStyle(
            'TableCellBold',
            parent=base_styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=7.5,
            leading=9.5,
            textColor=COLOR_PRIMARY_DARK,
            alignment=TA_LEFT,
        )

        styles['TableCellRight'] = ParagraphStyle(
            'TableCellRight',
            parent=base_styles['Normal'],
            fontName='Helvetica',
            fontSize=7.5,
            leading=9.5,
            textColor=COLOR_TEXT_MAIN,
            alignment=TA_RIGHT,
        )

        styles['TableCellRightBold'] = ParagraphStyle(
            'TableCellRightBold',
            parent=base_styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=7.5,
            leading=9.5,
            textColor=COLOR_PRIMARY_DARK,
            alignment=TA_RIGHT,
        )

        styles['TableCellCenter'] = ParagraphStyle(
            'TableCellCenter',
            parent=base_styles['Normal'],
            fontName='Helvetica',
            fontSize=7.5,
            leading=9.5,
            textColor=COLOR_TEXT_MAIN,
            alignment=TA_CENTER,
        )

        styles['KpiLabel'] = ParagraphStyle(
            'KpiLabel',
            parent=base_styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=7,
            leading=9,
            textColor=COLOR_TEXT_MUTED,
            alignment=TA_CENTER,
        )

        styles['KpiValue'] = ParagraphStyle(
            'KpiValue',
            parent=base_styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=11,
            leading=13,
            textColor=COLOR_PRIMARY_DARK,
            alignment=TA_CENTER,
        )

        return styles

    @classmethod
    def format_inr(cls, amount: Optional[Decimal], show_symbol: bool = True) -> str:
        """Deterministically formats INR currency amounts with standard decimal representation."""
        if amount is None:
            amount = Decimal('0.00')
        elif not isinstance(amount, Decimal):
            amount = Decimal(str(amount))

        symbol = "Rs. " if show_symbol else ""
        is_negative = amount < Decimal('0.00')
        abs_amount = abs(amount)
        formatted_num = f"{abs_amount:,.2f}"

        if is_negative:
            return f"-{symbol}{formatted_num}"
        return f"{symbol}{formatted_num}"

    @classmethod
    def format_date(cls, dt) -> str:
        """Formats dates as DD-MMM-YYYY."""
        if not dt:
            return "--"
        if hasattr(dt, 'strftime'):
            return dt.strftime('%d-%b-%Y')
        return str(dt)

    @classmethod
    def format_datetime(cls, dt) -> str:
        """Formats timestamp as DD-MMM-YYYY HH:MM."""
        if not dt:
            return "--"
        if hasattr(dt, 'strftime'):
            return dt.strftime('%d-%b-%Y %H:%M')
        return str(dt)

    @classmethod
    def create_letterhead(
        cls,
        report_title: str,
        period_str: Optional[str] = None,
        as_of_str: Optional[str] = None,
        generated_by_user: Optional[str] = None,
        version: str = "v1.0",
        usable_width: float = 523.0
    ) -> Table:
        """
        Creates an executive, high-contrast company letterhead with report metadata box.
        """
        profile = CompanyProfileService.get_profile()
        styles = cls.get_styles()

        # Left Column: Company Identity
        left_flowables = [
            Paragraph(profile.business_name.upper(), styles['CompanyName']),
            Paragraph(profile.legal_name, styles['CompanyLegal']),
            Paragraph(f"{profile.full_address} • Phone: {profile.phone}", styles['CompanyLegal']),
        ]
        if profile.gst_number or profile.tax_id:
            tax_parts = []
            if profile.gst_number:
                tax_parts.append(f"GSTIN: {profile.gst_number}")
            if profile.tax_id:
                tax_parts.append(f"PAN/Tax ID: {profile.tax_id}")
            left_flowables.append(Paragraph(" • ".join(tax_parts), styles['CompanyLegal']))

        # Right Column: Report Metadata Box
        now_str = cls.format_datetime(timezone.now())
        user_str = generated_by_user or "Authorized User"

        right_flowables = [
            Paragraph(report_title.upper(), styles['ReportTitle']),
        ]
        if period_str:
            right_flowables.append(Paragraph(f"Period: <b>{period_str}</b>", styles['MetaLabel']))
        if as_of_str:
            right_flowables.append(Paragraph(f"As of: <b>{as_of_str}</b>", styles['MetaLabel']))
        right_flowables.append(Paragraph(f"Generated: <b>{now_str}</b>", styles['MetaLabel']))
        right_flowables.append(Paragraph(f"Generated By: <b>{user_str}</b> • Rel: <b>{version}</b>", styles['MetaLabel']))

        header_table = Table(
            [[left_flowables, right_flowables]],
            colWidths=[usable_width * 0.58, usable_width * 0.42]
        )
        header_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
            ('TOPPADDING', (0, 0), (-1, -1), 0),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
        ]))

        return header_table

    @classmethod
    def create_kpi_summary_box(
        cls,
        items: List[Tuple[str, str, Optional[colors.Color]]],
        usable_width: float = 523.0
    ) -> Table:
        """
        Creates an executive financial KPI summary row (e.g. Total Billed, Total Paid, Balance Due).
        items: List of (Label, Value_Str, Optional_Text_Color)
        """
        styles = cls.get_styles()
        num_cols = len(items)
        col_w = usable_width / num_cols

        cell_data = []
        for label, val_str, val_color in items:
            val_style = ParagraphStyle(
                f'kpi_val_{label}',
                parent=styles['KpiValue'],
                textColor=val_color or COLOR_PRIMARY_DARK
            )
            cell_data.append([
                Paragraph(label.upper(), styles['KpiLabel']),
                Spacer(1, 2),
                Paragraph(val_str, val_style)
            ])

        kpi_table = Table([cell_data], colWidths=[col_w] * num_cols)
        kpi_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), COLOR_BG_LIGHT),
            ('BOX', (0, 0), (-1, -1), 1, COLOR_BORDER),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, COLOR_BORDER),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('LEFTPADDING', (0, 0), (-1, -1), 4),
            ('RIGHTPADDING', (0, 0), (-1, -1), 4),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        return kpi_table

    @classmethod
    def create_signature_block(
        cls,
        usable_width: float = 523.0,
        signatory_title: str = "Authorized Signatory"
    ) -> Table:
        """
        Creates a formal authorization stamp and signature block at the bottom of the statement.
        """
        profile = CompanyProfileService.get_profile()
        styles = cls.get_styles()

        left_cell = [
            Paragraph("<b>TERMS &amp; DECLARATION</b>", styles['BodyTextBold']),
            Paragraph(
                "1. This document is an official computer-generated statement of accounts.<br/>"
                "2. Please report any discrepancy within 7 days of statement issuance.<br/>"
                "3. Payments made via Cheque/Online Transfer are subject to bank realization.",
                styles['CompanyLegal']
            ),
        ]

        signatory_name = profile.authorized_signatory_name or "Managing Partner"
        signatory_desig = profile.authorized_signatory_designation or signatory_title

        right_cell = [
            Spacer(1, 15),
            Paragraph(f"For <b>{profile.business_name}</b>", styles['MetaValue']),
            Spacer(1, 25),
            Paragraph("_______________________________", styles['MetaLabel']),
            Paragraph(f"<b>{signatory_name}</b>", styles['MetaValue']),
            Paragraph(signatory_desig, styles['MetaLabel']),
        ]

        sig_table = Table([[left_cell, right_cell]], colWidths=[usable_width * 0.60, usable_width * 0.40])
        sig_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
        ]))
        return sig_table

    @classmethod
    def build_pdf_response(
        cls,
        elements: List[Any],
        filename: str,
        orientation: str = 'portrait'
    ) -> HttpResponse:
        """
        Renders the Platypus flowables into an A4 PDF HttpResponse using NumberedCanvas.
        """
        buffer = io.BytesIO()
        pagesize = landscape(A4) if orientation == 'landscape' else A4

        # Margins: 36pt (0.5 inch) all around
        doc = SimpleDocTemplate(
            buffer,
            pagesize=pagesize,
            leftMargin=36,
            rightMargin=36,
            topMargin=36,
            bottomMargin=42
        )

        doc.build(elements, canvasmaker=NumberedCanvas)

        buffer.seek(0)
        response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="{filename}"'
        return response
