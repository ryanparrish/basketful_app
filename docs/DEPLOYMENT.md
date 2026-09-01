# Basketful Production Deployment Guide

> Last updated: 2026-07-13

> **What's actually tracked in this repo vs. illustrative templates**: `docker-compose.prod.images.yml`, `docker-compose.frontend-admin.yml`, `docker-compose.frontend-participant.yml`, `render.yaml`, `Dockerfile`, `nginx/nginx.conf`, and `nginx/conf.d/basketful.conf` are real, committed files. There is **no** `docker-compose.prod.yml` in the repo — Option 1 below shows how you'd hand-roll one if you wanted local `dist/` volume mounts instead of pulling CI-built images; the repo's actual self-hosted path is Option 1 → step 5 (`docker-compose.prod.images.yml`). The real `nginx/conf.d/basketful.conf` is also simpler than the generic template in "Create Nginx Configuration" below — it proxies to Gunicorn/frontends directly and relies on the upstream load balancer for TLS and on S3 (`USE_S3=True`) for static/media, rather than serving `/static/`, `/media/` from local volumes. See the callout in that section for the real config. **Known gap**: `docker-compose.prod.images.yml` mounts `./nginx/conf.d/default.images.conf`, but no file by that name exists in the repo (only `nginx/conf.d/basketful.conf` does) — if you deploy via `docker-compose.prod.images.yml` as-is today, you need to add that file yourself.

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
      - DJANGO_ENV=prod
      - SECRET_KEY=${SECRET_KEY}
      - DATABASE_URL=${DATABASE_URL}
      - REDIS_URL=${REDIS_URL}
      - HASHIDS_SALT=${HASHIDS_SALT}
      - DOMAIN_NAME=${DOMAIN_NAME}
      - ALLOWED_HOSTS=${ALLOWED_HOSTS}
      - CSRF_TRUSTED_ORIGINS=${CSRF_TRUSTED_ORIGINS}
      - CORS_ALLOWED_ORIGINS=${CORS_ALLOWED_ORIGINS}
      - AUTH_COOKIE_DOMAIN=${AUTH_COOKIE_DOMAIN}
      - AUTH_COOKIE_SECURE=True
      - RECAPTCHA_PUBLIC_KEY=${RECAPTCHA_PUBLIC_KEY}
      - RECAPTCHA_PRIVATE_KEY=${RECAPTCHA_PRIVATE_KEY}
      - MAILGUN_API_KEY=${MAILGUN_API_KEY}
      - MAILGUN_SENDER_DOMAIN=${MAILGUN_SENDER_DOMAIN}
      - DEFAULT_FROM_EMAIL=${DEFAULT_FROM_EMAIL}
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
      - DJANGO_ENV=prod
      - SECRET_KEY=${SECRET_KEY}
      - DATABASE_URL=${DATABASE_URL}
      - REDIS_URL=${REDIS_URL}
      - HASHIDS_SALT=${HASHIDS_SALT}
      - MAILGUN_API_KEY=${MAILGUN_API_KEY}
      - MAILGUN_SENDER_DOMAIN=${MAILGUN_SENDER_DOMAIN}
      - DEFAULT_FROM_EMAIL=${DEFAULT_FROM_EMAIL}
    depends_on:
      - db
      - redis
    restart: unless-stopped

  # Celery Beat Scheduler — required for the 6 periodic tasks registered in
  # CELERY_BEAT_SCHEDULE (core/settings.py), e.g. weekly combined orders,
  # order-window notifications, low-inventory checks. Uses django-celery-beat's
  # DatabaseScheduler in production (see docker-compose.prod.images.yml).
  celery-beat:
    build:
      context: .
      dockerfile: Dockerfile
    command: celery -A core beat -l INFO --scheduler django_celery_beat.schedulers:DatabaseScheduler
    environment:
      - DEBUG=False
      - DJANGO_ENV=prod
      - SECRET_KEY=${SECRET_KEY}
      - DATABASE_URL=${DATABASE_URL}
      - REDIS_URL=${REDIS_URL}
      - HASHIDS_SALT=${HASHIDS_SALT}
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

> **The real, tracked config differs from the template below.** `nginx/nginx.conf` (base config: gzip, mime types, `include /etc/nginx/conf.d/*.conf`) and `nginx/conf.d/basketful.conf` are already committed to the repo and reflect the actual live deployment topology at `basketful.lovewm.org`:
> - TLS is terminated **upstream** (Linode NodeBalancer, Full Strict mode) — nginx itself only listens on plain HTTP `:80` and hardcodes `X-Forwarded-Proto: https` on the Django proxy (using `$scheme` there would be `http` and cause an infinite HTTPS redirect loop against Django's `SECURE_SSL_REDIRECT=True`).
> - `location /` proxies everything else (Django app + API + Django admin) to Gunicorn on `127.0.0.1:8080` — there's no separate `/api/` or `/django-admin/` location.
> - `location ^~ /new/admin/` proxies to the admin frontend container on `127.0.0.1:8081`.
> - `location ^~ /new/cart/` proxies to the participant frontend container on `127.0.0.1:8082`.
> - There are no `/static/` or `/media/` location blocks — static/media are served from S3-compatible object storage (`USE_S3=True`, see `core/settings.py`), not from local volumes.
>
> The template below is an alternative, fully self-hosted topology (no S3, TLS terminated locally via certbot, root path serves the participant frontend, `/admin/` serves the admin frontend) — use it if you're not using S3 and want nginx to terminate TLS itself. If you adapt it, keep in mind it does **not** match `nginx/conf.d/basketful.conf`, and the real path prefixes used by the CI-built frontend Docker images are `/new/admin/` and `/new/cart/` (baked in at build time — see [CI.md](CI.md)), not `/admin/` and `/`.

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

A real, tracked template already exists at **`.env.production.example`** in the repo root — copy it to `.env.production` and fill in real values rather than starting from scratch:

```bash
cp .env.production.example .env.production
```

Key fields (see the file itself for the complete, commented list):

```bash
# Django
SECRET_KEY=your-super-secret-key-generate-with-django
DEBUG=False
DJANGO_ENV=prod
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com
CSRF_TRUSTED_ORIGINS=https://yourdomain.com,https://www.yourdomain.com
CORS_ALLOWED_ORIGINS=https://yourdomain.com
DOMAIN_NAME=yourdomain.com
PARTICIPANT_FRONTEND_URL=https://shop.yourdomain.com
HASHIDS_SALT=your-random-salt-string

# Database
DATABASE_URL=postgresql://basketful:securepassword@db:5432/basketful
POSTGRES_DB=basketful
POSTGRES_USER=basketful
POSTGRES_PASSWORD=securepassword

# Redis (Celery broker/result backend and cache)
REDIS_URL=redis://redis:6379/0
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/0

# Security Cookies
AUTH_COOKIE_DOMAIN=.yourdomain.com
AUTH_COOKIE_SECURE=True
AUTH_COOKIE_SAMESITE=Lax

# reCAPTCHA (get from Google reCAPTCHA console)
RECAPTCHA_PUBLIC_KEY=your-site-key
RECAPTCHA_PRIVATE_KEY=your-secret-key

# Email — production ALWAYS uses django-anymail's Mailgun backend
# (core/settings.py hardcodes EMAIL_BACKEND when DJANGO_ENV=prod; SMTP
# settings such as EMAIL_HOST/EMAIL_HOST_PASSWORD are NOT read at all)
MAILGUN_API_KEY=your-mailgun-api-key
MAILGUN_SENDER_DOMAIN=mg.yourdomain.com
DEFAULT_FROM_EMAIL=Basketful <noreply@yourdomain.com>
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

`render.yaml` is already committed at the project root — Render will pick it up automatically as a Blueprint (`https://render.com/deploy`). It provisions, in region `oregon`, plan `starter` throughout:

- **`basketful-db`** — managed PostgreSQL
- **`basketful-redis`** — managed Redis (`type: redis`), used as both the Celery broker/result backend
- **`basketful-api`** — Django web service (`runtime: docker`, `dockerfilePath: ./Dockerfile`), `healthCheckPath: /api/health/`; `buildCommand` runs `pip install`, `collectstatic`, **and** `migrate --noinput`; `startCommand` runs `gunicorn core.wsgi:application --bind 0.0.0.0:$PORT --workers 2 --timeout 60 --max-requests 1000 --max-requests-jitter 100`
- **`basketful-worker`** — Celery worker (`dockerCommand: celery -A core worker -l INFO --concurrency=2`), shares `SECRET_KEY` from `basketful-api` via `fromService`
- **`basketful-admin`** — admin frontend static site (`buildCommand: cd frontend && npm ci && npm run build`, `staticPublishPath: frontend/dist`), `pullRequestPreviewsEnabled: true`
- **`basketful-shop`** — participant frontend static site (note: the service is named `basketful-shop` in `render.yaml`, **not** `basketful-participant`), same build pattern from `participant-frontend/`

Key env vars set in `render.yaml` for `basketful-api`: `DATABASE_URL` and `REDIS_URL` (both wired via `fromDatabase`/`fromService`), `SECRET_KEY` and `HASHIDS_SALT` (`generateValue: true`), `DEBUG=False`, `DJANGO_ENV=prod`, `ALLOWED_HOSTS=.onrender.com`, `CSRF_TRUSTED_ORIGINS=https://basketful-api.onrender.com`, `AUTH_COOKIE_SECURE=True`, `AUTH_COOKIE_SAMESITE=Lax`, and `RECAPTCHA_PUBLIC_KEY`/`RECAPTCHA_PRIVATE_KEY` (`sync: false` — set manually in the Render dashboard). Both static frontend services set `VITE_API_URL=https://basketful-api.onrender.com` at build time and add an `X-Frame-Options: SAMEORIGIN` header plus an SPA rewrite route (`/*` → `/index.html`).

Note: unlike the Docker Compose paths above, this Render blueprint does not set `MAILGUN_API_KEY`/`MAILGUN_SENDER_DOMAIN`/`DEFAULT_FROM_EMAIL` — add those manually in the Render dashboard if you need production email to work.

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

`VITE_API_URL` and `VITE_BASE_PATH` are **Vite build-time variables**, not runtime container env vars — they get compiled into the static JS bundle at `npm run build` / `vite build` time (see `frontend/vite.config.ts` `base` above, and the `ARG`/`ENV` lines in `frontend/Dockerfile` and `participant-frontend/Dockerfile`). How you set them depends on which deployment path you're using:

- **Building locally / on a VPS** (Option 1 step 4, Option 3): create `.env.production` in each frontend directory before running the build:

  **frontend/.env.production**:
  ```
  VITE_API_URL=https://yourdomain.com/api
  ```

  **participant-frontend/.env.production**:
  ```
  VITE_API_URL=https://yourdomain.com/api
  ```

- **Render static sites** (Option 2): set as `envVars` directly in `render.yaml` at build time (already wired to `https://basketful-api.onrender.com`).

- **Pulling the CI-built Docker images** (Option 1 step 5, `docker-compose.prod.images.yml`): these values are **already baked in** by `.github/workflows/frontend-ci.yml`'s `build-args` — `VITE_API_URL=/api/v1` and `VITE_BASE_PATH=/new/admin/` (admin) or `/new/cart/` (participant) for every branch/tag (see [CI.md](CI.md)). You cannot override them by setting env vars on the running container; you'd need to rebuild the image yourself with different `--build-arg` values if you need different paths.

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

### Real production routing (`nginx/conf.d/basketful.conf`)

| URL Path | Service | Description |
|----------|---------|-------------|
| `/` | Django (Gunicorn, `127.0.0.1:8080`) | Main app, Django admin, REST API — all unprefixed paths |
| `/new/admin/` | Admin Frontend (`127.0.0.1:8081`) | Staff dashboard (react-admin) |
| `/new/cart/` | Participant Frontend (`127.0.0.1:8082`) | Shopping portal |

Static/media are served from S3-compatible object storage (`USE_S3=True`), not from nginx.

### Self-hosted template (Option 1's generic `nginx/conf.d/default.conf`, no S3)

| URL Path | Service | Description |
|----------|---------|-------------|
| `/` | Participant Frontend | Shopping portal |
| `/admin/` | Admin Frontend | Staff dashboard |
| `/django-admin/` | Django Admin | Super admin |
| `/api/` | Django API | REST endpoints |
| `/static/` | Static Files | CSS, JS, images |
| `/media/` | Media Files | Uploaded content |
