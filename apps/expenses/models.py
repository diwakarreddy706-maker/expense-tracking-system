from django.db import models


class ExpenseCategory(models.Model):
    """
    Hierarchical classification of business expenses.
    Defined in DATABASE_SCHEMA.md.
    """
    name = models.CharField(max_length=100, unique=True, db_index=True)
    code = models.CharField(max_length=30, unique=True, db_index=True)
    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='subcategories',
        help_text="Optional parent category for hierarchical grouping"
    )
    color_hex = models.CharField(max_length=7, default='#10B981', help_text="Hex color for UI charts")
    icon_class = models.CharField(max_length=50, default='bi-receipt', help_text="Bootstrap icon class")
    is_active = models.BooleanField(default=True, db_index=True)
    is_deleted = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'expense_categories'
        verbose_name = 'Expense Category'
        verbose_name_plural = 'Expense Categories'
        ordering = ['name']

    def __str__(self):
        if self.parent:
            return f"{self.parent.name} → {self.name} ({self.code})"
        return f"{self.name} ({self.code})"
