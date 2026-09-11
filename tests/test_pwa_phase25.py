"""
PHASE 25 — PROGRESSIVE WEB APP (PWA) & INSTALL-TO-PHONE AUTOMATED TEST SUITE
Project: Sri Basaveshwara / Sri Basaveshwara Harvesting & Co.
Tests:
- Web App Manifest JSON validity & required metadata
- Shortcut URL validity matching actual Django reverse routing
- Physical icon files integrity, PNG format, and exact dimensions
- Service Worker caching contracts & financial safety rules
- Base template PWA integration and Mobile Install triggers
"""

import json
import os
from PIL import Image
from django.test import TestCase, SimpleTestCase
from django.urls import reverse
from django.conf import settings


class PwaManifestTests(SimpleTestCase):
    """Verifies that manifest.webmanifest is valid, well-structured, and production-safe."""

    def setUp(self):
        self.manifest_path = os.path.join(settings.BASE_DIR, 'static', 'manifest.webmanifest')

    def test_manifest_file_exists_and_is_valid_json(self):
        self.assertTrue(os.path.exists(self.manifest_path), "manifest.webmanifest does not exist in static/")
        with open(self.manifest_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        self.assertIsInstance(data, dict)

    def test_manifest_required_fields(self):
        with open(self.manifest_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        self.assertEqual(data.get('name'), "Sri Basaveshwara Harvesting & Co. — Harvesting ERP")
        self.assertEqual(data.get('short_name'), "Sri Basaveshwara")
        self.assertEqual(data.get('display'), "standalone")
        self.assertEqual(data.get('orientation'), "portrait-primary")
        self.assertEqual(data.get('start_url'), "/")
        self.assertEqual(data.get('scope'), "/")
        self.assertEqual(data.get('theme_color'), "#10B981")
        self.assertEqual(data.get('background_color'), "#0B0F17")
        self.assertIn("agriculture", data.get('categories', []))
        self.assertIn("finance", data.get('categories', []))

    def test_manifest_shortcuts_match_django_named_routes(self):
        with open(self.manifest_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        shortcuts = data.get('shortcuts', [])
        self.assertGreaterEqual(len(shortcuts), 4, "Must define at least 4 operational shortcuts")

        shortcut_urls = {s.get('name'): s.get('url') for s in shortcuts}

        # Verify against live Django reverse URLs
        self.assertEqual(shortcut_urls.get('Record Expense'), reverse('expenses:create'))
        self.assertEqual(shortcut_urls.get('Log Fuel Refill'), reverse('fuel:create'))
        self.assertEqual(shortcut_urls.get('New Work Log'), reverse('machines:work_create'))
        self.assertEqual(shortcut_urls.get('Farmer Ledger (Udhar)'), reverse('machines:farmer_ledger'))


class PwaIconsTests(SimpleTestCase):
    """Verifies that all referenced PWA icons physically exist and have valid dimensions."""

    def test_icon_dimensions_and_validity(self):
        icons_to_test = {
            'icon-192.png': (192, 192),
            'icon-512.png': (512, 512),
            'favicon-32x32.png': (32, 32),
            'favicon-16x16.png': (16, 16),
            'logo.png': (1024, 1024),
        }

        for filename, expected_size in icons_to_test.items():
            filepath = os.path.join(settings.BASE_DIR, 'static', 'icons', filename)
            self.assertTrue(os.path.exists(filepath), f"Icon file missing: {filename}")

            with Image.open(filepath) as img:
                self.assertEqual(img.format, 'PNG', f"Icon {filename} must be valid PNG format")
                self.assertEqual(img.size, expected_size, f"Icon {filename} size must be {expected_size}, got {img.size}")


class PwaServiceWorkerTests(SimpleTestCase):
    """Verifies Service Worker integrity, versioning, and strict financial safety contracts."""

    def setUp(self):
        self.sw_path = os.path.join(settings.BASE_DIR, 'static', 'js', 'service-worker.js')

    def test_service_worker_file_exists(self):
        self.assertTrue(os.path.exists(self.sw_path), "service-worker.js does not exist in static/js/")

    def test_service_worker_version_and_contracts(self):
        with open(self.sw_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Check version
        self.assertIn("sbh-pwa-v3.2", content, "Service Worker must declare version sbh-pwa-v3.2")

        # Check safety: Non-GET requests must strictly bypass cache
        self.assertIn("request.method !== 'GET'", content)

        # Check safety: Must provide offline fallback explaining network requirement
        self.assertIn("You are currently offline", content)
        self.assertIn("financial transactions and ledger records require an active internet connection", content)

        # Check safety: Skip waiting message handler
        self.assertIn("skipWaiting", content)


class PwaClientIntegrationTests(TestCase):
    """Verifies client template integration, PWA meta tags, and install triggers."""

    def test_base_template_has_pwa_tags(self):
        response = self.client.get(reverse('accounts:login'))
        self.assertEqual(response.status_code, 200)

        html = response.content.decode('utf-8')

        # Manifest link
        self.assertIn('rel="manifest"', html)
        self.assertIn('manifest.webmanifest', html)

        # Theme & Mobile Web App Meta Tags
        self.assertIn('name="theme-color"', html)
        self.assertIn('name="apple-mobile-web-app-capable"', html)
        self.assertIn('name="mobile-web-app-capable"', html)
        self.assertIn('name="apple-mobile-web-app-title"', html)

        # Icons
        self.assertIn('apple-touch-icon', html)

    def test_quick_add_modal_has_install_trigger(self):
        modal_template_path = os.path.join(settings.BASE_DIR, 'templates', 'components', 'quick_add_modal.html')
        self.assertTrue(os.path.exists(modal_template_path))

        with open(modal_template_path, 'r', encoding='utf-8') as f:
            modal_content = f.read()

        self.assertIn('pwa-install-trigger', modal_content)
        self.assertIn('window.triggerPwaInstall()', modal_content)
