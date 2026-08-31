"""
Gunicorn production configuration for Expense Tracking & Management System.
"""

import multiprocessing
import os

# Server socket
port = os.getenv("PORT", "8000")
bind = os.getenv("GUNICORN_BIND", f"0.0.0.0:{port}")
backlog = 2048

# Worker processes
# Standard formula: 2-4 x $(NUM_CORES)
cpu_count = multiprocessing.cpu_count()
workers = int(os.getenv("GUNICORN_WORKERS", str(cpu_count * 2 + 1)))
worker_class = "gthread"
threads = int(os.getenv("GUNICORN_THREADS", "2"))
worker_connections = 1000

# Worker lifecycle & memory leak prevention
timeout = int(os.getenv("GUNICORN_TIMEOUT", "60"))
keepalive = int(os.getenv("GUNICORN_KEEPALIVE", "5"))
max_requests = int(os.getenv("GUNICORN_MAX_REQUESTS", "1000"))
max_requests_jitter = int(os.getenv("GUNICORN_MAX_REQUESTS_JITTER", "100"))
graceful_timeout = 30

# Process naming
proc_name = "expense_tracking_wsgi"

# Server mechanics
daemon = False
pidfile = os.getenv("GUNICORN_PID_FILE", None)
umask = 0
user = None
group = None

# Logging
accesslog = os.getenv("GUNICORN_ACCESS_LOG", "-")  # stdout by default, file in systemd
errorlog = os.getenv("GUNICORN_ERROR_LOG", "-")    # stderr by default, file in systemd
loglevel = os.getenv("GUNICORN_LOG_LEVEL", "info")
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)sµs'
capture_output = True
