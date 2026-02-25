# Basketful Production Deployment Guide

This guide covers deploying the Basketful application to production, including:
- Django backend API
- Admin frontend (staff dashboard)
- Participant frontend (customer shopping portal)

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        Load Balancer / CDN                       │
│                    (Cloudflare, AWS ALB, etc.)                   │
└─────────────────────────────────────────────────────────────────┘
                                 │
         ┌───────────────────────┼───────────────────────┐
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐   ┌─────────────────┐   ┌─────────────────┐
│  /admin/*       │   │  /api/*         │   │  /app/* or /    │
│  Admin Frontend │   │  Django API     │   │  Participant    │
│  (React SPA)    │   │  + Django Admin │   │  Frontend (SPA) │
└─────────────────┘   └─────────────────┘   └─────────────────┘
         │                       │                       │
         │              ┌────────┴────────┐              │
         │              │                 │              │
         │              ▼                 ▼              │
         │     ┌─────────────┐   ┌─────────────┐        │
         │     │  PostgreSQL │   │    Redis    │        │
         │     │  Database   │   │   (Cache)   │        │
         │     └─────────────┘   └─────────────┘        │
         │                                               │
         └───────────────────────────────────────────────┘
                    Static Assets via S3/CDN
```

## Deployment Options

### Option 1: Docker Compose (Self-Hosted)
Best for: VPS, dedicated servers, on-premise

### Option 2: Platform as a Service
Best for: Render, Railway, Fly.io, Heroku

### Option 3: Kubernetes
Best for: Large scale, enterprise deployments

---

## Option 1: Docker Compose Deployment

### Prerequisites
- Docker & Docker Compose installed
- Domain name with DNS configured
- SSL certificate (Let's Encrypt recommended)

### 1. Create Production Docker Compose

Create `docker-compose.prod.yml` in project root:

```yaml
version: '3.8'

services:
  # Django API Backend
  api:
    build:
      context: .
      dockerfile: Dockerfile
    command: gunicorn core.wsgi:application --bind 0.0.0.0:8000 --workers 4
    volumes:
      - static_volume:/code/staticfiles
      - media_volume:/code/media
    environment:
      - DEBUG=False
      - SECRET_KEY=${SECRET_KEY}
      - DATABASE_URL=${DATABASE_URL}
      - REDIS_URL=${REDIS_URL}
      - ALLOWED_HOSTS=${ALLOWED_HOSTS}
      - CSRF_TRUSTED_ORIGINS=${CSRF_TRUSTED_ORIGINS}
      - CORS_ALLOWED_ORIGINS=${CORS_ALLOWED_ORIGINS}
      - AUTH_COOKIE_DOMAIN=${AUTH_COOKIE_DOMAIN}
      - AUTH_COOKIE_SECURE=True
      - RECAPTCHA_PUBLIC_KEY=${RECAPTCHA_PUBLIC_KEY}
      - RECAPTCHA_PRIVATE_KEY=${RECAPTCHA_PRIVATE_KEY}
    depends_on:
      - db
      - redis
    restart: unless-stopped

  # Celery Worker
  celery:
    build:
      context: .
      dockerfile: Dockerfile
    command: celery -A core worker -l INFO
    environment:
      - DEBUG=False
      - SECRET_KEY=${SECRET_KEY}
      - DATABASE_URL=${DATABASE_URL}
      - REDIS_URL=${REDIS_URL}
    depends_on:
      - db
      - redis
    restart: unless-stopped

  # Celery Beat Scheduler
  celery-beat:
    build:
      context: .
      dockerfile: Dockerfile
    command: celery -A core beat -l INFO
    environment:
      - DEBUG=False
      - SECRET_KEY=${SECRET_KEY}
      - DATABASE_URL=${DATABASE_URL}
      - REDIS_URL=${REDIS_URL}
    depends_on:
      - db
      - redis
    restart: unless-stopped

  # PostgreSQL Database
  db:
    image: postgres:15-alpine
    volumes:
      - postgres_data:/var/lib/postgresql/data
    environment:
      - POSTGRES_DB=basketful
      - POSTGRES_USER=${POSTGRES_USER}
      - POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
    restart: unless-stopped

  # Redis Cache
  redis:
    image: redis:7-alpine
    volumes:
      - redis_data:/data
    restart: unless-stopped

  # Nginx Reverse Proxy
  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro
      - ./nginx/conf.d:/etc/nginx/conf.d:ro
      - ./certbot/conf:/etc/letsencrypt:ro
      - ./certbot/www:/var/www/certbot:ro
      - static_volume:/var/www/static:ro
      - media_volume:/var/www/media:ro
      - ./frontend/dist:/var/www/admin:ro
      - ./participant-frontend/dist:/var/www/participant:ro
    depends_on:
      - api
    restart: unless-stopped

volumes:
  postgres_data:
  redis_data:
  static_volume:
  media_volume:
```

### 2. Create Nginx Configuration

Create `nginx/conf.d/default.conf`:

```nginx
upstream django {
    server api:8000;
}

# Redirect HTTP to HTTPS
server {
    listen 80;
    server_name yourdomain.com;
    
    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }
    
    location / {
        return 301 https://$host$request_uri;
    }
}

# Main HTTPS Server
server {
    listen 443 ssl http2;
    server_name yourdomain.com;

    ssl_certificate /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;
    
    # SSL Security
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256;
    ssl_prefer_server_ciphers off;

    # Security Headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;

    # Django API
    location /api/ {
        proxy_pass http://django;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Cookie $http_cookie;
        proxy_cookie_path / "/; HttpOnly; Secure; SameSite=Lax";
    }

    # Django Admin
    location /django-admin/ {
        proxy_pass http://django;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Static files
    location /static/ {
        alias /var/www/static/;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    # Media files
    location /media/ {
        alias /var/www/media/;
        expires 1M;
        add_header Cache-Control "public";
    }

    # Admin Frontend (Staff Dashboard)
    location /admin/ {
        alias /var/www/admin/;
        try_files $uri $uri/ /admin/index.html;
        expires 1h;
    }

    # Participant Frontend (Shopping Portal) - Root
    location / {
        alias /var/www/participant/;
        try_files $uri $uri/ /index.html;
        expires 1h;
    }
}
```

### 3. Create Production Environment File

Create `.env.production`:

```bash
# Django
SECRET_KEY=your-super-secret-key-generate-with-django
DEBUG=False
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com
CSRF_TRUSTED_ORIGINS=https://yourdomain.com,https://www.yourdomain.com
CORS_ALLOWED_ORIGINS=https://yourdomain.com

# Database
DATABASE_URL=postgresql://basketful:securepassword@db:5432/basketful
POSTGRES_USER=basketful
POSTGRES_PASSWORD=securepassword

# Redis
REDIS_URL=redis://redis:6379/0

# Security Cookies
AUTH_COOKIE_DOMAIN=.yourdomain.com
AUTH_COOKIE_SECURE=True
AUTH_COOKIE_SAMESITE=Lax

# reCAPTCHA (get from Google reCAPTCHA console)
RECAPTCHA_PUBLIC_KEY=your-site-key
RECAPTCHA_PRIVATE_KEY=your-secret-key

# Email (configure your SMTP provider)
EMAIL_HOST=smtp.sendgrid.net
EMAIL_PORT=587
EMAIL_HOST_USER=apikey
EMAIL_HOST_PASSWORD=your-sendgrid-api-key
DEFAULT_FROM_EMAIL=noreply@yourdomain.com
```

### 4. Build and Deploy

```bash
# Build frontend assets
cd frontend
npm ci && npm run build
cd ../participant-frontend
npm ci && npm run build
cd ..

# Start services
docker-compose -f docker-compose.prod.yml --env-file .env.production up -d --build

# Run migrations
docker-compose -f docker-compose.prod.yml exec api python manage.py migrate

# Collect static files
docker-compose -f docker-compose.prod.yml exec api python manage.py collectstatic --noinput

# Create superuser
docker-compose -f docker-compose.prod.yml exec api python manage.py createsuperuser
```

### 5. Deploy Using Pulled Frontend Images (No Local `dist` Mounts)

Use this if you want Docker Compose to pull the frontend images built by CI:

- `${DOCKER_USERNAME}/basketful-admin`
- `${DOCKER_USERNAME}/basketful-participant`

Add to `.env.production`:

```bash
DOCKER_USERNAME=your-dockerhub-username
FRONTEND_IMAGE_TAG=latest
```

For production release pinning, set `FRONTEND_IMAGE_TAG` to a released version (example: `1.2.3`) that came from a git tag push like `v1.2.3`.

Deploy:

```bash
docker-compose -f docker-compose.prod.images.yml --env-file .env.production pull
docker-compose -f docker-compose.prod.images.yml --env-file .env.production up -d --build
```

This uses:

- `docker-compose.prod.images.yml`
- `nginx/conf.d/default.images.conf`

### 6. Run Frontends as Separate Compose Stacks

If you want admin and participant frontends fully separate from backend compose, run:

```bash
# Admin frontend only
docker-compose -f docker-compose.frontend-admin.yml --env-file .env.production pull
docker-compose -f docker-compose.frontend-admin.yml --env-file .env.production up -d

# Participant frontend only
docker-compose -f docker-compose.frontend-participant.yml --env-file .env.production pull
docker-compose -f docker-compose.frontend-participant.yml --env-file .env.production up -d
```

Required env vars:

```bash
DOCKER_USERNAME=your-dockerhub-username
FRONTEND_IMAGE_TAG=latest
ADMIN_FRONTEND_PORT=8081
PARTICIPANT_FRONTEND_PORT=8082
```

Compose files:

- `docker-compose.frontend-admin.yml`
- `docker-compose.frontend-participant.yml`

---

## Option 2: Platform as a Service (Render)

### Render.com Deployment

Create `render.yaml` in project root:

```yaml
databases:
  - name: basketful-db
    databaseName: basketful
    user: basketful
    plan: starter

services:
  # Django API
  - type: web
    name: basketful-api
    runtime: docker
    dockerfilePath: ./Dockerfile
    envVars:
      - key: DATABASE_URL
        fromDatabase:
          name: basketful-db
          property: connectionString
      - key: SECRET_KEY
        generateValue: true
      - key: DEBUG
        value: "False"
      - key: ALLOWED_HOSTS
        value: ".onrender.com"
      - key: AUTH_COOKIE_SECURE
        value: "True"
      - key: RECAPTCHA_PUBLIC_KEY
        sync: false
      - key: RECAPTCHA_PRIVATE_KEY
        sync: false
    buildCommand: pip install -r requirements.txt && python manage.py collectstatic --noinput
    startCommand: gunicorn core.wsgi:application --bind 0.0.0.0:$PORT

  # Admin Frontend
  - type: web
    name: basketful-admin
    runtime: static
    buildCommand: cd frontend && npm ci && npm run build
    staticPublishPath: frontend/dist
    envVars:
      - key: VITE_API_URL
        value: https://basketful-api.onrender.com
    routes:
      - type: rewrite
        source: /*
        destination: /index.html

  # Participant Frontend  
  - type: web
    name: basketful-participant
    runtime: static
    buildCommand: cd participant-frontend && npm ci && npm run build
    staticPublishPath: participant-frontend/dist
    envVars:
      - key: VITE_API_URL
        value: https://basketful-api.onrender.com
    routes:
      - type: rewrite
        source: /*
        destination: /index.html

  # Celery Worker
  - type: worker
    name: basketful-worker
    runtime: docker
    dockerfilePath: ./Dockerfile
    dockerCommand: celery -A core worker -l INFO
    envVars:
      - key: DATABASE_URL
        fromDatabase:
          name: basketful-db
          property: connectionString
      - key: SECRET_KEY
        sync: false
```

---

## Option 3: Manual VPS Deployment

### For Ubuntu/Debian Server

### 1. Server Setup

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install dependencies
sudo apt install -y python3.12 python3.12-venv python3-pip nginx certbot python3-certbot-nginx postgresql redis-server

# Create app user
sudo useradd -m -s /bin/bash basketful
sudo su - basketful
```

### 2. Clone and Setup

```bash
# Clone repository
git clone https://github.com/yourusername/basketful_app.git
cd basketful_app

# Create virtual environment
python3.12 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
pip install gunicorn

# Build frontends
cd frontend && npm ci && npm run build && cd ..
cd participant-frontend && npm ci && npm run build && cd ..

# Setup environment
cp .env.example .env
nano .env  # Edit with production values

# Run migrations
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py createsuperuser
```

### 3. Create Systemd Services

Create `/etc/systemd/system/basketful.service`:

```ini
[Unit]
Description=Basketful Django API
After=network.target

[Service]
User=basketful
Group=www-data
WorkingDirectory=/home/basketful/basketful_app
Environment="PATH=/home/basketful/basketful_app/venv/bin"
EnvironmentFile=/home/basketful/basketful_app/.env
ExecStart=/home/basketful/basketful_app/venv/bin/gunicorn \
    --access-logfile - \
    --workers 4 \
    --bind unix:/run/gunicorn/basketful.sock \
    core.wsgi:application

[Install]
WantedBy=multi-user.target
```

Create `/etc/systemd/system/basketful-celery.service`:

```ini
[Unit]
Description=Basketful Celery Worker
After=network.target

[Service]
User=basketful
Group=www-data
WorkingDirectory=/home/basketful/basketful_app
Environment="PATH=/home/basketful/basketful_app/venv/bin"
EnvironmentFile=/home/basketful/basketful_app/.env
ExecStart=/home/basketful/basketful_app/venv/bin/celery \
    -A core worker -l INFO

[Install]
WantedBy=multi-user.target
```

### 4. Enable Services

```bash
sudo systemctl daemon-reload
sudo systemctl enable basketful basketful-celery
sudo systemctl start basketful basketful-celery
```

---

## Frontend Build Configuration

### Update Vite Config for Production

**frontend/vite.config.ts** (Admin):

```typescript
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  base: '/admin/',  // Serve from /admin/ path
  build: {
    outDir: 'dist',
    sourcemap: false,
  },
});
```

**participant-frontend/vite.config.ts** (Participant):

```typescript
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  base: '/',  // Serve from root
  build: {
    outDir: 'dist',
    sourcemap: false,
  },
});
```

### Environment Variables for Frontends

Create `.env.production` in each frontend:

**frontend/.env.production**:
```
VITE_API_URL=https://yourdomain.com/api
```

**participant-frontend/.env.production**:
```
VITE_API_URL=https://yourdomain.com/api
```

---

## Security Checklist

Before going live, ensure:

- [ ] `DEBUG=False` in Django settings
- [ ] Strong `SECRET_KEY` (generate new one for production)
- [ ] `ALLOWED_HOSTS` properly configured
- [ ] SSL/TLS certificate installed
- [ ] `AUTH_COOKIE_SECURE=True`
- [ ] `AUTH_COOKIE_SAMESITE=Lax` or `Strict`
- [ ] Production reCAPTCHA keys (not test keys)
- [ ] CORS properly configured
- [ ] CSRF trusted origins set
- [ ] Database backups configured
- [ ] Error monitoring (Sentry) configured
- [ ] Rate limiting enabled
- [ ] Security headers in nginx

---

## Monitoring & Maintenance

### Health Checks

```bash
# Check API health
curl https://yourdomain.com/api/health/

# Check services
docker-compose -f docker-compose.prod.yml ps
# Image-based frontend deployment:
docker-compose -f docker-compose.prod.images.yml ps
```

### Logs

```bash
# View API logs
docker-compose -f docker-compose.prod.yml logs -f api

# View Celery logs
docker-compose -f docker-compose.prod.yml logs -f celery
# Image-based frontend deployment:
docker-compose -f docker-compose.prod.images.yml logs -f nginx
```

### Updates

```bash
# Pull latest code
git pull origin main

# Rebuild and restart
docker-compose -f docker-compose.prod.yml up -d --build

# Run migrations
docker-compose -f docker-compose.prod.yml exec api python manage.py migrate
# Image-based frontend deployment:
docker-compose -f docker-compose.prod.images.yml exec api python manage.py migrate
```

---

## Troubleshooting

### Cookie Issues
- Ensure `AUTH_COOKIE_DOMAIN` matches your domain
- Check that `AUTH_COOKIE_SECURE=True` when using HTTPS
- Verify CORS allows credentials

### Static Files Not Loading
- Run `collectstatic` after deployment
- Check nginx static file paths
- Verify file permissions

### 502 Bad Gateway
- Check if gunicorn is running
- Verify socket path matches nginx config
- Check gunicorn logs for errors

---

## Quick Reference

| URL Path | Service | Description |
|----------|---------|-------------|
| `/` | Participant Frontend | Shopping portal |
| `/admin/` | Admin Frontend | Staff dashboard |
| `/django-admin/` | Django Admin | Super admin |
| `/api/` | Django API | REST endpoints |
| `/static/` | Static Files | CSS, JS, images |
| `/media/` | Media Files | Uploaded content |
