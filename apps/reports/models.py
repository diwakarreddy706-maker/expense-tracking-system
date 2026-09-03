from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User


class CompanyProfile(models.Model):
    """
    Configurable Business / Company profile for official report headers,
    letterheads, and invoices.
    """
    business_name = models.CharField(
        max_length=150,
        default='Sri Basaveshwara Harvesting & Co',
        help_text="Primary business trade name"
    )
    legal_name = models.CharField(
        max_length=200,
        default='Sri Basaveshwara Agricultural Contractor Services',
        blank=True,
        help_text="Registered legal entity name"
    )
    phone = models.CharField(max_length=50, default='+91 98765 43210', blank=True)
    email = models.EmailField(max_length=100, default='contact@basaveshwara-harvesting.com', blank=True)
    village = models.CharField(max_length=100, default='Harapanahalli Road', blank=True)
    taluk = models.CharField(max_length=100, default='Harapanahalli', blank=True)
    district = models.CharField(max_length=100, default='Vijayanagara', blank=True)
    state = models.CharField(max_length=100, default='Karnataka', blank=True)
    pin_code = models.CharField(max_length=20, default='583131', blank=True)
    gst_number = models.CharField(max_length=30, blank=True, null=True, help_text="GSTIN if applicable")
    tax_id = models.CharField(max_length=30, blank=True, null=True, help_text="PAN / State Tax ID")
    authorized_signatory_name = models.CharField(max_length=100, default='Managing Partner', blank=True)
    authorized_signatory_designation = models.CharField(max_length=100, default='Authorized Signatory', blank=True)
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'company_profiles'
        verbose_name = 'Company Profile'
        verbose_name_plural = 'Company Profiles'

    def __str__(self):
        return self.business_name

    @property
    def full_address(self) -> str:
        parts = [self.village, self.taluk, f"{self.district} - {self.pin_code}", self.state]
        return ", ".join([p for p in parts if p])


class ReportAuditLog(models.Model):
    """
    Lightweight read-only audit log for financial report generation.
    Strictly NOT a financial transaction. Tracks report requests for governance.
    """
    TYPE_FARMER_STATEMENT = 'FARMER_STATEMENT'
    TYPE_PAYMENT_RECEIPT = 'PAYMENT_RECEIPT'
    TYPE_WORK_INVOICE = 'WORK_INVOICE'
    TYPE_MACHINERY_PNL = 'MACHINERY_PNL'
    TYPE_EXPENSE_ANALYSIS = 'EXPENSE_ANALYSIS'
    TYPE_RECEIVABLES_AGING = 'RECEIVABLES_AGING'
    TYPE_FINANCIAL_AUDIT = 'FINANCIAL_AUDIT'

    REPORT_TYPE_CHOICES = [
        (TYPE_FARMER_STATEMENT, 'Farmer Account Statement PDF'),
        (TYPE_PAYMENT_RECEIPT, 'Payment / Advance Receipt PDF'),
        (TYPE_WORK_INVOICE, 'Work Entry / Invoice PDF'),
        (TYPE_MACHINERY_PNL, 'Machinery Operational P&L PDF'),
        (TYPE_EXPENSE_ANALYSIS, 'Expense Analysis PDF'),
        (TYPE_RECEIVABLES_AGING, 'Farmer Receivables Aging PDF'),
        (TYPE_FINANCIAL_AUDIT, 'Financial Audit Statement PDF'),
    ]

    report_type = models.CharField(max_length=50, choices=REPORT_TYPE_CHOICES, db_index=True)
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='report_audit_logs'
    )
    generated_at = models.DateTimeField(auto_now_add=True, db_index=True)
    related_object_id = models.BigIntegerField(null=True, blank=True, db_index=True)
    report_period_start = models.DateField(null=True, blank=True)
    report_period_end = models.DateField(null=True, blank=True)
    as_of_date = models.DateField(default=timezone.now)
    success = models.BooleanField(default=True)
    file_name = models.CharField(max_length=255, blank=True)
    metadata_json = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = 'report_audit_logs'
        verbose_name = 'Report Audit Log'
        verbose_name_plural = 'Report Audit Logs'
        ordering = ['-generated_at', '-id']

    def __str__(self):
        user_str = self.user.username if self.user else 'System'
        return f"[{self.generated_at:%Y-%m-%d %H:%M}] {self.get_report_type_display()} by {user_str}"
