"""
WSGI config for expense_tracking_project.
"""

import os
from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'expense_tracking_core.settings.development')

application = get_wsgi_application()
