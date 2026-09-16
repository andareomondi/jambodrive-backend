# Cosmara Backend Setup Guide

## Overview
This is a production-ready Django REST Framework backend for Cosmara car rental platform. It replaces the Supabase + Vercel stack with a custom backend on DigitalOcean.

---

## 1. PROJECT STRUCTURE

```
cosmara_backend/
├── manage.py
├── cosmara_backend/
│   ├── settings.py
│   ├── urls.py
│   ├── wsgi.py
│   └── asgi.py
├── api/                          # NEW: API app
│   ├── migrations/
│   ├── admin.py
│   ├── apps.py
│   ├── models.py                 # Use cosmara_models.py content
│   ├── serializers.py            # Use cosmara_serializers.py content
│   ├── views.py                  # Use cosmara_views.py content
│   ├── urls.py                   # Use cosmara_urls.py content
│   ├── filters.py                # Optional: custom filters
│   ├── permissions.py            # Already in cosmara_views.py
│   └── tests.py
├── users/                        # NEW: Custom user app
│   ├── models.py
│   ├── admin.py
│   └── signals.py                # Auto-create Profile on User creation
├── requirements.txt
├── .env.example
└── docker-compose.yml            # Optional: local development
```

---

## 2. INSTALLATION STEPS

### 2.1 Create Django Project
```bash
# Create project directory
mkdir cosmara_backend && cd cosmara_backend

# Create virtual environment
python3.11 -m venv venv
source venv/bin/activate  # or: venv\Scripts\activate on Windows

# Create Django project
django-admin startproject cosmara_backend .
django-admin startapp api
django-admin startapp users
```

### 2.2 Install Dependencies
```bash
pip install --upgrade pip

# Core dependencies
pip install django==4.2.0
pip install djangorestframework==3.14.0
pip install django-cors-headers==4.3.0
pip install python-decouple==3.8
pip install psycopg2-binary==2.9.9

# Advanced features
pip install drf-spectacular==0.27.0          # OpenAPI/Swagger docs
pip install django-filter==23.4              # Filtering
pip install django-extensions==3.2.3         # Management commands
pip install python-dateutil==2.8.2

# M-Pesa integration (later)
pip install requests==2.31.0

# Production
pip install gunicorn==21.2.0
pip install whitenoise==6.6.0               # Static files

# Development
pip install pytest==7.4.0
pip install pytest-django==4.7.0
pip install black==23.12.0
pip install flake8==6.1.0

# Save requirements
pip freeze > requirements.txt
```

### 2.3 Configure Django Settings

**cosmara_backend/settings.py:**
```python
import os
from pathlib import Path
from decouple import config

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = config('SECRET_KEY', default='dev-key-change-in-production')
DEBUG = config('DEBUG', default=True, cast=bool)
ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='localhost,127.0.0.1').split(',')

# Installed apps
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    
    # Third-party
    'rest_framework',
    'corsheaders',
    'drf_spectacular',
    'django_filters',
    
    # Local apps
    'api.apps.ApiConfig',
    'users.apps.UsersConfig',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',  # Static files
    'django.contrib.sessions.middleware.SessionMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'cosmara_backend.urls'

# Database
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': config('DB_NAME', default='cosmara'),
        'USER': config('DB_USER', default='postgres'),
        'PASSWORD': config('DB_PASSWORD', default=''),
        'HOST': config('DB_HOST', default='localhost'),
        'PORT': config('DB_PORT', default='5432'),
    }
}

# REST Framework
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.TokenAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticatedOrReadOnly',
    ],
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
}

# CORS
CORS_ALLOWED_ORIGINS = config(
    'CORS_ALLOWED_ORIGINS',
    default='http://localhost:3000,http://localhost:8000'
).split(',')

# Static files
STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# Logging
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '[{levelname}] {asctime} {module} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'file': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': os.path.join(BASE_DIR, 'logs', 'django.log'),
            'formatter': 'verbose',
        },
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console', 'file'],
        'level': 'INFO',
    },
}

# Time zone
USE_TZ = True
TIME_ZONE = 'Africa/Nairobi'
```

### 2.4 Create .env File
```bash
# .env
DEBUG=True
SECRET_KEY=your-secret-key-here

# Database
DB_NAME=cosmara
DB_USER=postgres
DB_PASSWORD=your-db-password
DB_HOST=localhost
DB_PORT=5432

# CORS
CORS_ALLOWED_ORIGINS=http://localhost:3000,http://localhost:8000,https://cosmara.co.ke

# M-Pesa (later)
MPESA_CONSUMER_KEY=your-key
MPESA_CONSUMER_SECRET=your-secret
MPESA_PASSKEY=your-passkey
MPESA_SHORTCODE=your-shortcode
```

### 2.5 Set Up URLs

**cosmara_backend/urls.py:**
```python
from django.contrib import admin
from django.urls import path, include
from drf_spectacular.views import SpectacularSwaggerView, SpectacularAPIView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/v1/', include('api.urls')),
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema')),
]
```

### 2.6 Copy Model Files

Replace the content of `api/models.py`, `api/serializers.py`, and `api/views.py` with the generated files (cosmara_models.py, cosmara_serializers.py, cosmara_views.py).

Copy `cosmara_urls.py` content into `api/urls.py`.

### 2.7 Set Up User Signals

**users/apps.py:**
```python
from django.apps import AppConfig

class UsersConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'users'
    
    def ready(self):
        import users.signals
```

**users/signals.py:**
```python
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from api.models import Profile

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """Auto-create Profile when User is created"""
    if created:
        Profile.objects.create(
            user=instance,
            full_name=instance.get_full_name() or instance.username,
        )

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    """Save Profile when User is saved"""
    if hasattr(instance, 'profile'):
        instance.profile.save()
```

### 2.8 Database Migrations

```bash
# Make migrations
python manage.py makemigrations api users

# Run migrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser
```

### 2.9 Verify Installation

```bash
# Run development server
python manage.py runserver

# Visit:
# http://localhost:8000/api/docs/           <- Swagger UI
# http://localhost:8000/admin/               <- Django Admin
# http://localhost:8000/api/v1/health/       <- Health check
```

---

## 3. API ENDPOINTS

All endpoints are documented at: `/api/docs/`

**Key endpoints:**
- `GET /api/v1/cars/` - Browse cars
- `POST /api/v1/bookings/` - Create booking
- `POST /api/v1/cars/search/` - Search with filters
- `POST /api/v1/cars/availability/` - Check availability
- `POST /api/v1/bookings/mpesa_callback/` - M-Pesa webhook

---

## 4. ADMIN SETUP

Django admin gives you free management UI:

**api/admin.py:**
```python
from django.contrib import admin
from .models import Profile, Car, Booking, Review, GalleryEvent, SupportRequest

@admin.register(Car)
class CarAdmin(admin.ModelAdmin):
    list_display = ['name', 'model', 'price', 'available', 'rating']
    list_filter = ['available', 'car_type', 'fuel']
    search_fields = ['name', 'model']

@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ['id', 'car', 'profile', 'status', 'pickup_date', 'total_price']
    list_filter = ['status', 'created_at']
    search_fields = ['car__name', 'profile__full_name']

@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ['full_name', 'email', 'role', 'total_bookings']
    list_filter = ['role', 'join_date']
    search_fields = ['full_name', 'user__email']

admin.site.register(Review)
admin.site.register(GalleryEvent)
admin.site.register(SupportRequest)
```

---

## 5. DEPLOYMENT CHECKLIST

### Local Development
- [ ] Virtual environment created
- [ ] Dependencies installed
- [ ] .env file configured
- [ ] Database migrated
- [ ] Superuser created
- [ ] API docs accessible
- [ ] CORS configured for frontend

### DigitalOcean Deployment
- [ ] Droplet created (Ubuntu 22.04, 4GB RAM)
- [ ] PostgreSQL installed and configured
- [ ] Gunicorn installed
- [ ] Nginx configured as reverse proxy
- [ ] SSL certificate installed (Let's Encrypt)
- [ ] Environment variables set
- [ ] Backups configured
- [ ] Monitoring set up (Uptime Robot, Sentry)

### Post-Deployment
- [ ] Frontend CORS updated
- [ ] M-Pesa webhook URL updated
- [ ] Database backups scheduled
- [ ] Logs rotation configured
- [ ] Security headers set
- [ ] Rate limiting configured

---

## 6. PRODUCTION DEPLOYMENT

### Gunicorn Configuration
```bash
# gunicorn_config.py
workers = 4
worker_class = "sync"
worker_connections = 1000
timeout = 30
bind = "0.0.0.0:8000"
```

### Nginx Configuration
```nginx
upstream cosmara {
    server 127.0.0.1:8000;
}

server {
    listen 80;
    server_name api.cosmara.co.ke;
    
    location /static/ {
        alias /home/cosmara/cosmara_backend/staticfiles/;
    }
    
    location / {
        proxy_pass http://cosmara;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### Systemd Service
```ini
# /etc/systemd/system/cosmara.service
[Unit]
Description=Cosmara Django Backend
After=network.target

[Service]
Type=notify
User=cosmara
WorkingDirectory=/home/cosmara/cosmara_backend
ExecStart=/home/cosmara/cosmara_backend/venv/bin/gunicorn \
    --config gunicorn_config.py \
    cosmara_backend.wsgi

Restart=always
RestartSec=5s

[Install]
WantedBy=multi-user.target
```

---

## 7. TESTING

```bash
# Run tests
python manage.py test api

# With coverage
pip install coverage
coverage run --source='api' manage.py test api
coverage report
```

---

## 8. COMMON ISSUES

**PostgreSQL connection error:**
```bash
# Install PostgreSQL
sudo apt-get install postgresql postgresql-contrib

# Start service
sudo service postgresql start

# Create database
sudo -u postgres createdb cosmara
```

**Static files not found:**
```bash
python manage.py collectstatic --noinput
```

**Migrations not applied:**
```bash
python manage.py showmigrations  # See status
python manage.py migrate api      # Apply specific app
```

---

## 9. MONITORING & MAINTENANCE

### Health Check
```bash
curl http://localhost:8000/api/v1/health/
```

### Database Backup
```bash
pg_dump -U postgres cosmara > backup_$(date +%Y%m%d).sql
```

### Log Rotation
```bash
# /etc/logrotate.d/cosmara
/var/log/cosmara/*.log {
    daily
    rotate 7
    compress
    delaycompress
    notifempty
}
```

---

## 10. NEXT STEPS

1. ✅ Set up Django project
2. ✅ Create models and serializers
3. ⏭️ Integrate M-Pesa payment
4. ⏭️ Set up authentication (JWT or Token)
5. ⏭️ Configure image serving (DO Spaces)
6. ⏭️ Deploy to DigitalOcean
7. ⏭️ Connect Next.js frontend
8. ⏭️ Set up monitoring and alerts

---

**Questions?** Check the generated models, serializers, and views files for implementation details.
