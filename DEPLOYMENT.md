# Production Deployment & Operations Guide

**Project:** Expense Tracking & Management System (`expense_tracking`)  
**Database:** MySQL 8.0.46 (InnoDB, UTF8MB4, Asia/Kolkata Timezone)  
**Framework:** Django 5.x on Python 3.11+

---

## 1. System Architecture

The production deployment runs with **Nginx** as the reverse proxy and SSL termination gateway, **Gunicorn** as the WSGI application server, and a local/managed **MySQL 8.0** database instance.

```
[ Web Clients / Mobile ]
           │ (HTTPS 443)
           ▼
     [ NGINX Proxy ]
     ├── /static/  ──────► Static Assets Directory
     ├── /media/   ──────► Uploaded Media Files
     └── / (WSGI)  ──────► [ GUNICORN (127.0.0.1:8000) ]
                                   │
                                   ▼
                       [ Django Application Core ]
                                   │
                                   ▼
                       [ MySQL 8.0 (InnoDB) ]
```

---

## 2. Environment Configuration (`.env`)

Create a production `.env` file in the project root directory. **Never commit `.env` to Git.**

```ini
# Core Django Configuration
DJANGO_SETTINGS_MODULE=expense_tracking_core.settings.production
SECRET_KEY=your-cryptographically-secure-random-secret-key
DEBUG=False
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com,127.0.0.1

# MySQL 8.0 Database Configuration
DB_NAME=expense_tracking_db
DB_USER=expense_user
DB_PASSWORD=your_secure_mysql_password
DB_HOST=127.0.0.1
DB_PORT=3306

# Production SSL & Cookie Security
SECURE_SSL_REDIRECT=True
SESSION_COOKIE_SECURE=True
CSRF_COOKIE_SECURE=True
```

---

## 3. Database Initialization & Setup

```bash
# Log in to MySQL 8.0 as root
mysql -u root -p

# Execute initialization commands
CREATE DATABASE expense_tracking_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'expense_user'@'127.0.0.1' IDENTIFIED BY 'your_secure_mysql_password';
GRANT ALL PRIVILEGES ON expense_tracking_db.* TO 'expense_user'@'127.0.0.1';
FLUSH PRIVILEGES;
EXIT;
```

---

## 4. Application Installation & Build

```bash
# 1. Clone repository
git clone <repo_url> /var/www/expense_tracking
cd /var/www/expense_tracking

# 2. Set up virtual environment
python3 -m venv venv
source venv/bin/activate

# 3. Install production dependencies
pip install --upgrade pip
pip install -r requirements.txt
pip install gunicorn

# 4. Run database migrations
python manage.py migrate

# 5. Collect static assets
python manage.py collectstatic --noinput

# 6. Verify security configuration
python manage.py check --deploy
```

---

## 5. Gunicorn Service Configuration

Create systemd service `/etc/systemd/system/expense_tracking.service`:

```ini
[Unit]
Description=Gunicorn daemon for Expense Tracking & Management System
After=network.target mysql.service

[Service]
User=www-data
Group=www-data
WorkingDirectory=/var/www/expense_tracking
ExecStart=/var/www/expense_tracking/venv/bin/gunicorn \
          --workers 4 \
          --bind 127.0.0.1:8000 \
          --access-logfile /var/log/expense_tracking/access.log \
          --error-logfile /var/log/expense_tracking/error.log \
          expense_tracking_core.wsgi:application
Restart=always

[Install]
WantedBy=multi-user.target
```

Enable and start the service:
```bash
sudo systemctl daemon-reload
sudo systemctl enable expense_tracking
sudo systemctl start expense_tracking
```

---

## 6. Nginx Server Configuration

Create Nginx site configuration `/etc/nginx/sites-available/expense_tracking`:

```nginx
server {
    listen 80;
    server_name yourdomain.com www.yourdomain.com;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name yourdomain.com www.yourdomain.com;

    ssl_certificate /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;

    # Security Headers
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-Frame-Options "DENY" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    add_header Content-Security-Policy "default-src 'self'; script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://fonts.googleapis.com; font-src 'self' https://cdn.jsdelivr.net https://fonts.gstatic.com; img-src 'self' data:;" always;

    # Static Assets
    location /static/ {
        alias /var/www/expense_tracking/staticfiles/;
        expires 30d;
        access_log off;
    }

    # Media Uploads
    location /media/ {
        alias /var/www/expense_tracking/media/;
        expires 30d;
        access_log off;
    }

    # Application Proxy
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

---

## 7. Backup & Disaster Recovery Procedures

### Automated Database Backup Script (`/usr/local/bin/backup_ets_db.sh`)
```bash
#!/bin/bash
BACKUP_DIR="/var/backups/expense_tracking"
DATE=$(date +%Y%m%d_%H%M%S)
mkdir -p $BACKUP_DIR

# Dump MySQL database with single transaction for consistency
mysqldump -u expense_user -p'your_secure_mysql_password' \
          --single-transaction \
          --quick \
          --routines \
          --triggers \
          expense_tracking_db | gzip > $BACKUP_DIR/db_backup_$DATE.sql.gz

# Retain backups for 30 days
find $BACKUP_DIR -type f -name "db_backup_*.sql.gz" -mtime +30 -delete
```

### Database Restore Procedure
```bash
# 1. Unzip backup archive
gunzip < /var/backups/expense_tracking/db_backup_YYYYMMDD_HHMMSS.sql.gz > /tmp/restore.sql

# 2. Restore into MySQL
mysql -u expense_user -p expense_tracking_db < /tmp/restore.sql

# 3. Clean up temporary file
rm /tmp/restore.sql
```
