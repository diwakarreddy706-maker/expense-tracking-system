from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User
from decimal import Decimal
from apps.expenses.models import ExpenseCategory
from apps.machines.models import Machine


class Budget(models.Model):
    """
    Monthly Operational & Capital Budgets by Business Segment.
    Defined in DATABASE_SCHEMA.md (Table 11).
    """
    SEGMENT_GENERAL = 'GENERAL'
    SEGMENT_FARM = 'FARM_OPERATIONS'
    SEGMENT_RENTAL = 'MACHINERY_RENTAL'
    SEGMENT_WORKSHOP = 'WORKSHOP_REPAIRS'
    SEGMENT_RETAIL = 'SHOP_RETAIL'
    SEGMENT_ADMIN = 'GENERAL_ADMIN'

    SEGMENT_CHOICES = [
        (SEGMENT_GENERAL, 'General Combined Operations'),
        (SEGMENT_FARM, 'Farm Operations & Cultivation'),
        (SEGMENT_RENTAL, 'Machinery Custom Hiring & Rental'),
        (SEGMENT_WORKSHOP, 'Workshop & Fleet Maintenance'),
        (SEGMENT_RETAIL, 'Retail Counter & Agrochemicals'),
        (SEGMENT_ADMIN, 'General Administration & Overhead'),
    ]

    STATUS_DRAFT = 'DRAFT'
    STATUS_ACTIVE = 'ACTIVE'
    STATUS_CLOSED = 'CLOSED'
    STATUS_CANCELLED = 'CANCELLED'

    STATUS_CHOICES = [
        (STATUS_DRAFT, 'Draft'),
        (STATUS_ACTIVE, 'Active'),
        (STATUS_CLOSED, 'Closed'),
        (STATUS_CANCELLED, 'Cancelled'),
    ]

    title = models.CharField(max_length=100, help_text="e.g. August 2026 Fleet Operations Budget")
    period_month = models.PositiveSmallIntegerField(help_text="Month (1-12)", db_index=True)
    period_year = models.PositiveSmallIntegerField(help_text="Year (e.g. 2026)", db_index=True)
    business_segment = models.CharField(
        max_length=30,
        choices=SEGMENT_CHOICES,
        default=SEGMENT_GENERAL,
        db_index=True
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_ACTIVE,
        db_index=True
    )
    notes = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name='created_budgets')
    is_deleted = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'budgets'
        verbose_name = 'Budget'
        verbose_name_plural = 'Budgets'
        ordering = ['-period_year', '-period_month', 'title']
        unique_together = [('period_month', 'period_year', 'business_segment')]

    def __str__(self):
        return f"{self.title} ({self.period_month:02d}/{self.period_year} - {self.get_business_segment_display()})"

    @property
    def total_allocated_amount(self) -> Decimal:
        """Returns total planned amount across all budget items."""
        total = self.items.aggregate(s=models.Sum('allocated_amount'))['s'] or Decimal('0.00')
        return total.quantize(Decimal('0.01'))


class BudgetItem(models.Model):
    """
    Granular category / machine specific budget allocation item.
    Defined in DATABASE_SCHEMA.md (Table 11).
    """
    budget = models.ForeignKey(Budget, on_delete=models.CASCADE, related_name='items')
    category = models.ForeignKey(ExpenseCategory, on_delete=models.RESTRICT, related_name='budget_items')
    machine = models.ForeignKey(Machine, on_delete=models.SET_NULL, null=True, blank=True, related_name='budget_items')
    allocated_amount = models.DecimalField(max_digits=15, decimal_places=2)
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'budget_items'
        verbose_name = 'Budget Allocation Item'
        verbose_name_plural = 'Budget Allocation Items'
        ordering = ['category__name', 'machine__machine_code']
        unique_together = [('budget', 'category', 'machine')]

    def __str__(self):
        machine_label = f" ({self.machine.machine_code})" if self.machine else ""
        return f"{self.category.name}{machine_label}: ₹{self.allocated_amount}"
