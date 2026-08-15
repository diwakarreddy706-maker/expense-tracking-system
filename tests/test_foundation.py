"""
Phase 1 Foundation Test Suite.
Validates Django configuration, health check, template rendering,
and basic calculation services.
"""

from decimal import Decimal
from django.test import TestCase, SimpleTestCase, Client
from django.urls import reverse
from django.conf import settings
from apps.finance.services.balance_service import FinancialCalculationService


class FoundationConfigurationTests(SimpleTestCase):
    """Verifies baseline Django settings and configuration."""

    def test_settings_loaded(self):
        """Verifies core Django settings are active."""
        self.assertEqual(settings.TIME_ZONE, 'Asia/Kolkata')
        self.assertTrue(settings.USE_TZ)
        self.assertIn('apps.dashboard.apps.DashboardConfig', settings.INSTALLED_APPS)
        self.assertIn('apps.finance.apps.FinanceConfig', settings.INSTALLED_APPS)
        self.assertIn('apps.expenses.apps.ExpensesConfig', settings.INSTALLED_APPS)

    def test_static_and_media_configured(self):
        """Verifies static and media settings are configured properly."""
        self.assertEqual(settings.STATIC_URL, '/static/')
        self.assertEqual(settings.MEDIA_URL, '/media/')
        self.assertTrue(settings.STATIC_ROOT is not None)
        self.assertTrue(settings.MEDIA_ROOT is not None)


class FoundationRoutingAndViewsTests(SimpleTestCase):
    """Verifies health check and root views."""

    def setUp(self):
        self.client = Client()

    def test_health_check_endpoint(self):
        """Verifies /health/ endpoint returns HTTP 200 and healthy status."""
        response = self.client.get(reverse('health_check'))
        self.assertEqual(response.status_code, 200)
        json_data = response.json()
        self.assertEqual(json_data.get('status'), 'healthy')
        self.assertIn('Expense Tracking & Management System', json_data.get('application', ''))

    def test_dashboard_root_view(self):
        """Verifies root / renders executive dashboard template."""
        response = self.client.get(reverse('dashboard:index'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'dashboard/index.html')
        self.assertTemplateUsed(response, 'base.html')
        self.assertContains(response, 'Executive Dashboard')
        self.assertContains(response, 'Total Balance')
        self.assertContains(response, "Today's Financial Summary")

    def test_dashboard_api_summary(self):
        """Verifies dashboard API summary responds."""
        response = self.client.get(reverse('dashboard:api_summary'))
        self.assertEqual(response.status_code, 200)
        json_data = response.json()
        self.assertEqual(json_data.get('status'), 'foundation_ready')


class FinancialServiceFoundationTests(SimpleTestCase):
    """Verifies Rule 1 and Rule 10 financial calculation engine foundation."""

    def test_decimal_precision(self):
        """Verifies fixed-point decimal precision calculations."""
        opening = Decimal('125430.50')
        inflow = Decimal('25000.75')
        outflow = Decimal('4870.25')
        transfer_in = Decimal('5000.00')
        transfer_out = Decimal('2000.00')

        expected = FinancialCalculationService.calculate_scoped_closing(
            opening_balance=opening,
            inflow=inflow,
            outflow=outflow,
            transfer_in=transfer_in,
            transfer_out=transfer_out
        )
        self.assertEqual(expected, Decimal('148561.00'))

    def test_discrepancy_calculation(self):
        """Verifies variance math between actual and expected closing."""
        actual = Decimal('148500.00')
        expected = Decimal('148561.00')
        discrepancy = FinancialCalculationService.calculate_discrepancy(actual, expected)
        self.assertEqual(discrepancy, Decimal('-61.00'))
