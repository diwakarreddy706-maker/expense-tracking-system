"""
ASGI config for expense_tracking_project.
"""

import os
from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'expense_tracking_core.settings.development')

application = get_asgi_application()
