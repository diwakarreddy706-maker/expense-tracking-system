import os
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from apps.accounts.models import UserProfile
from apps.machines.models import Machine, MachineBooking, MachineType
from apps.finance.models import Customer

User = get_user_model()

class MobileFieldEnhancementsTest(TestCase):
    """
    Validates the 4 Mobile Field Enhancements:
    1. One-Tap WhatsApp Payment Receipts & Balance Reminders
    2. Field Quick-Dial & Instant Farmer Search
    3. High-Contrast Outdoor Sunlight Mode & Night Mode
    4. Quick Field Remarks & Voice-to-Text Helper
    """

    def setUp(self):
        self.client = Client()
        self.owner = User.objects.create_user(
            username='field_owner',
            password='Password123!',
            first_name='Basaveshwara',
            last_name='Owner'
        )
        self.owner.profile.role = 'OWNER'
        self.owner.profile.save()

        self.customer = Customer.objects.create(
            name='Siddaramaiah Gowda',
            phone='9880123456',
            customer_code='FARM-001',
            location_address='Gangavati',
            notes='S/O Sharanappa'
        )

        self.m_type = MachineType.objects.create(name='Combine Harvester', code='HARV-01')
        self.machine = Machine.objects.create(
            machine_code='MCH-001',
            name='Kubota Harvester 01',
            machine_type=self.m_type,
            registration_no='KA-37-M-1122',
            hourly_rate=2500,
            status='ACTIVE'
        )

        self.client.login(username='field_owner', password='Password123!')

    def test_static_assets_exist(self):
        """Verify field-helpers.js exists and has core functionality."""
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        js_path = os.path.join(base_dir, 'static', 'js', 'field-helpers.js')
        self.assertTrue(os.path.exists(js_path), "field-helpers.js must exist in static/js/")

        with open(js_path, 'r', encoding='utf-8') as f:
            content = f.read()

        self.assertIn('sendWhatsAppMessage', content)
        self.assertIn('sendWhatsAppReminder', content)
        self.assertIn('sendWhatsAppReceipt', content)
        self.assertIn('toggleVoiceDictation', content)
        self.assertIn('insertQuickChip', content)
        self.assertIn('setTheme', content)
        self.assertIn('sunlight', content)

    def test_base_template_loads_helpers_and_sunlight_theme(self):
        """Verify base.html initializes 3-way theme and loads field-helpers.js."""
        response = self.client.get(reverse('dashboard:index'))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')
        self.assertIn('field-helpers.js', content)
        self.assertIn('sunlight', content)
        self.assertIn('cycleTheme()', content)

    def test_farmer_ledger_whatsapp_and_quick_dial(self):
        """Verify farmer ledger screen includes WhatsApp reminder and Call buttons."""
        response = self.client.get(reverse('machines:farmer_ledger_detail', args=[self.customer.id]))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')

        # WhatsApp and Call links
        self.assertIn('sendWhatsAppReminder', content)
        self.assertIn('tel:', content)
        self.assertIn('farmerSearchInput', content)
        self.assertIn('farmerSearchClearBtn', content)
        self.assertIn('searchCounterBadge', content)

    def test_work_entry_form_quick_chips_and_mic(self):
        """Verify work entry form contains Quick Chips and Voice Mic Dictation."""
        response = self.client.get(reverse('machines:work_create'))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')

        self.assertIn('toggleVoiceDictation', content)
        self.assertIn('insertQuickChip', content)
        self.assertIn('Paddy Harvest', content)
        self.assertIn('Muddy Field', content)

    def test_fuel_form_quick_chips_and_mic(self):
        """Verify fuel intake form contains Quick Chips and Voice Mic Dictation."""
        response = self.client.get(reverse('fuel:create'))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')

        self.assertIn('toggleVoiceDictation', content)
        self.assertIn('insertQuickChip', content)
        self.assertIn('Full Tank', content)
        self.assertIn('IOCL Gangavati', content)

    def test_expense_form_quick_chips_and_mic(self):
        """Verify expense recording form contains Quick Chips and Voice Mic Dictation."""
        response = self.client.get(reverse('expenses:create'))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')

        self.assertIn('toggleVoiceDictation', content)
        self.assertIn('insertQuickChip', content)
        self.assertIn('Grease &amp; Oil', content)
        self.assertIn('Blade Sharpening', content)

    def test_maintenance_job_form_quick_chips_and_mic(self):
        """Verify maintenance form contains Quick Chips and Voice Mic Dictation."""
        response = self.client.get(reverse('machines:maintenance_job_create'))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')

        self.assertIn('toggleVoiceDictation', content)
        self.assertIn('insertQuickChip', content)
        self.assertIn('Cutter Blade', content)
        self.assertIn('Hydraulic Leak', content)

    def test_customer_directory_quick_dial(self):
        """Verify customer list directory contains tel: call links and WhatsApp actions."""
        response = self.client.get(reverse('finance:customers'))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')

        self.assertIn('tel:9880123456', content)
        self.assertIn('sendWhatsAppMessage', content)
        self.assertIn(reverse('machines:farmer_ledger_detail', args=[self.customer.id]), content)

    def test_booking_detail_quick_dial_and_whatsapp(self):
        """Verify booking detail has call link and WhatsApp direct message."""
        booking = MachineBooking.objects.create(
            booking_code='BKG-001',
            customer=self.customer,
            machine_type=self.m_type,
            work_date='2026-09-15',
            billing_type='ACRE',
            expected_quantity=10,
            status='CONFIRMED',
            created_by=self.owner
        )
        response = self.client.get(reverse('machines:booking_detail', args=[booking.id]))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')
        self.assertIn('tel:9880123456', content)
        self.assertIn('sendWhatsAppMessage', content)

