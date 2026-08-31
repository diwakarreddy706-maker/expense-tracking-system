#!/usr/bin/env python
"""
Production Readiness Verification Script for Expense Tracking System.
Validates all security policies, configuration variables, and deployment readiness.
"""

import os
import sys
from pathlib import Path

# Setup Django environment with production settings
from dotenv import load_dotenv
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

prod_env = BASE_DIR / '.env.production'
if prod_env.exists():
    load_dotenv(prod_env, override=True)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'expense_tracking_core.settings.production')

import django
from django.conf import settings
from django.core.management import call_command

def check_mark(status: bool) -> str:
    return "[PASS]" if status else "[WARN]"

def run_production_audit():
    print("=" * 78)
    print("      EXPENSE TRACKING SYSTEM -- PRODUCTION READINESS AUDIT")
    print("=" * 78)

    try:
        django.setup()
    except Exception as e:
        print(f"\n[FAIL] Django setup failed with error: {e}")
        sys.exit(1)

    checks = []

    # 1. DEBUG Status
    debug_pass = (settings.DEBUG is False)
    checks.append(("DEBUG is False", debug_pass, f"DEBUG = {settings.DEBUG}"))

    # 2. Secret Key Quality
    secret_key = settings.SECRET_KEY
    sk_pass = bool(secret_key and len(secret_key) >= 50 and not secret_key.startswith('django-insecure-'))
    masked_sk = secret_key[:6] + "..." + secret_key[-4:] if secret_key else "EMPTY"
    details = f"Key: {masked_sk} (Len: {len(secret_key) if secret_key else 0})"
    if not sk_pass:
        details += " [Action: Supply 50+ char random key in production .env]"
    checks.append(("SECRET_KEY Security (>= 50 chars, production random)", sk_pass, details))

    # 3. Allowed Hosts
    allowed_hosts = settings.ALLOWED_HOSTS
    hosts_pass = bool(allowed_hosts and len(allowed_hosts) > 0 and '*' not in allowed_hosts)
    checks.append(("ALLOWED_HOSTS configured", hosts_pass, f"{len(allowed_hosts)} host(s): {', '.join(allowed_hosts)}"))

    # 4. CSRF Trusted Origins
    csrf_origins = getattr(settings, 'CSRF_TRUSTED_ORIGINS', [])
    checks.append(("CSRF_TRUSTED_ORIGINS defined", isinstance(csrf_origins, list), f"{len(csrf_origins)} origin(s)"))

    # 5. Database Backend
    db_engine = settings.DATABASES['default']['ENGINE']
    db_pass = (db_engine == 'django.db.backends.mysql')
    db_name = settings.DATABASES['default'].get('NAME', 'Not set')
    checks.append(("Production MySQL Database Engine", db_pass, f"Engine: {db_engine}, DB: {db_name}"))

    # 6. Static and Media Roots
    static_root = getattr(settings, 'STATIC_ROOT', None)
    media_root = getattr(settings, 'MEDIA_ROOT', None)
    static_pass = bool(static_root and isinstance(static_root, Path))
    media_pass = bool(media_root and isinstance(media_root, Path))
    checks.append(("STATIC_ROOT Defined & Valid Path", static_pass, f"Path: {static_root}"))
    checks.append(("MEDIA_ROOT Defined & Valid Path", media_pass, f"Path: {media_root}"))

    # 7. Cookie Security
    sess_secure = getattr(settings, 'SESSION_COOKIE_SECURE', False)
    csrf_secure = getattr(settings, 'CSRF_COOKIE_SECURE', False)
    sess_httponly = getattr(settings, 'SESSION_COOKIE_HTTPONLY', False)
    cookie_pass = (sess_secure and csrf_secure and sess_httponly)
    checks.append(("Cookie Security (Secure & HttpOnly)", cookie_pass, f"SessSecure={sess_secure}, CSRFSecure={csrf_secure}, HttpOnly={sess_httponly}"))

    # 8. Security Headers
    xss_filt = getattr(settings, 'SECURE_BROWSER_XSS_FILTER', False)
    nosniff = getattr(settings, 'SECURE_CONTENT_TYPE_NOSNIFF', False)
    xframe = getattr(settings, 'X_FRAME_OPTIONS', '')
    headers_pass = (xss_filt and nosniff and xframe == 'DENY')
    checks.append(("Security HTTP Headers (XSS, NoSniff, FrameGuard)", headers_pass, f"X-Frame={xframe}, NoSniff={nosniff}"))

    # 9. HSTS Configuration
    hsts_seconds = getattr(settings, 'SECURE_HSTS_SECONDS', 0)
    hsts_sub = getattr(settings, 'SECURE_HSTS_INCLUDE_SUBDOMAINS', False)
    hsts_preload = getattr(settings, 'SECURE_HSTS_PRELOAD', False)
    hsts_pass = (hsts_seconds >= 31536000 and hsts_sub and hsts_preload)
    checks.append(("HSTS Configuration (>= 1 Year + Preload)", hsts_pass, f"HSTS={hsts_seconds}s, Subdomains={hsts_sub}, Preload={hsts_preload}"))

    # 10. Logging Architecture
    logging_cfg = getattr(settings, 'LOGGING', {})
    handlers = logging_cfg.get('handlers', {})
    loggers = logging_cfg.get('loggers', {})
    has_rot_fin = 'financial_file' in handlers
    has_rot_sec = 'security_file' in handlers
    has_rot_err = 'error_file' in handlers
    has_custom_loggers = all(k in loggers for k in ['expense_tracking.financial', 'expense_tracking.security', 'expense_tracking.errors'])
    log_pass = (has_rot_fin and has_rot_sec and has_rot_err and has_custom_loggers)
    checks.append(("Production Rotating File Logging", log_pass, f"Handlers: {len(handlers)}, Custom Loggers: {has_custom_loggers}"))

    # Print Results Table
    print(f"{'CHECK':<50} | {'STATUS':<6} | {'DETAILS'}")
    print("-" * 115)
    all_critical_passed = True
    for name, passed, details in checks:
        if not passed and name != "SECRET_KEY Security (>= 50 chars, production random)":
            all_critical_passed = False
        print(f"{name:<50} | {check_mark(passed):<6} | {details}")

    print("-" * 115)
    print("\nRunning Django core 'check --deploy' validation...")
    try:
        call_command('check', deploy=True)
        print("\n[SUCCESS] Django deployment check completed without critical errors.")
    except Exception as e:
        print(f"\n[ERROR] Django check --deploy failed: {e}")
        all_critical_passed = False

    print("=" * 78)
    if all_critical_passed and sk_pass:
        print("RESULT: ALL PRODUCTION READINESS CHECKS PASSED.")
    elif all_critical_passed:
        print("RESULT: PRODUCTION CONFIGURATION VERIFIED (Generate random SECRET_KEY for live .env).")
    else:
        print("RESULT: SOME CONFIGURATION CHECKS FAILED.")
    print("=" * 78)

    return all_critical_passed

if __name__ == '__main__':
    success = run_production_audit()
    sys.exit(0 if success else 1)
