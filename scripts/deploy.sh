#!/bin/bash
# =============================================================================
# Basketful Production Deployment Script
# =============================================================================
# Usage: ./scripts/deploy.sh [environment]
# Environments: docker, render
# =============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
ENVIRONMENT="${1:-docker}"

echo "🚀 Basketful Deployment Script"
echo "================================"
echo "Environment: $ENVIRONMENT"
echo "Project Dir: $PROJECT_DIR"
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Functions
log_success() { echo -e "${GREEN}✓ $1${NC}"; }
log_warning() { echo -e "${YELLOW}⚠ $1${NC}"; }
log_error() { echo -e "${RED}✗ $1${NC}"; }

check_prerequisites() {
    echo "Checking prerequisites..."
    
    if ! command -v docker &> /dev/null; then
        log_error "Docker is not installed"
        exit 1
    fi
    log_success "Docker installed"
    
    if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
        log_error "Docker Compose is not installed"
        exit 1
    fi
    log_success "Docker Compose installed"
    
    if ! command -v npm &> /dev/null; then
        log_error "npm is not installed"
        exit 1
    fi
    log_success "npm installed"
    
    if [ ! -f "$PROJECT_DIR/.env.production" ]; then
        log_warning ".env.production not found"
        echo "  Copy .env.production.example to .env.production and configure it"
        exit 1
    fi
    log_success ".env.production exists"
    
    echo ""
}

build_frontends() {
    echo "Building frontend assets..."
    
    # Admin frontend
    echo "  Building admin frontend..."
    cd "$PROJECT_DIR/frontend"
    npm ci --silent
    npm run build
    log_success "Admin frontend built"
    
    # Participant frontend
    echo "  Building participant frontend..."
    cd "$PROJECT_DIR/participant-frontend"
    npm ci --silent
    npm run build
    log_success "Participant frontend built"
    
    cd "$PROJECT_DIR"
    echo ""
}

deploy_docker() {
    echo "Deploying with Docker Compose..."
    
    # Create required directories
    mkdir -p "$PROJECT_DIR/nginx/conf.d"
    mkdir -p "$PROJECT_DIR/certbot/conf"
    mkdir -p "$PROJECT_DIR/certbot/www"
    
    # Stop existing containers
    docker-compose -f docker-compose.prod.yml down || true
    
    # Build and start containers
    docker-compose -f docker-compose.prod.yml --env-file .env.production up -d --build
    
    echo ""
    log_success "Containers started"
    
    # Wait for database to be ready
    echo "Waiting for database..."
    sleep 10
    
    # Run migrations
    echo "Running database migrations..."
    docker-compose -f docker-compose.prod.yml exec -T api python manage.py migrate --noinput
    log_success "Migrations complete"
    
    # Collect static files
    echo "Collecting static files..."
    docker-compose -f docker-compose.prod.yml exec -T api python manage.py collectstatic --noinput
    log_success "Static files collected"
    
    echo ""
    echo "================================"
    log_success "Deployment complete!"
    echo ""
    echo "Services status:"
    docker-compose -f docker-compose.prod.yml ps
    echo ""
    echo "Next steps:"
    echo "  1. Configure SSL certificates with Let's Encrypt"
    echo "  2. Update nginx/conf.d/default.conf with your domain"
    echo "  3. Create admin user: docker-compose -f docker-compose.prod.yml exec api python manage.py createsuperuser"
    echo ""
}

deploy_render() {
    echo "Deploying to Render.com..."
    
    if ! command -v render &> /dev/null; then
        log_warning "Render CLI not installed"
        echo ""
        echo "To deploy to Render:"
        echo "  1. Push your code to GitHub"
        echo "  2. Go to https://dashboard.render.com"
        echo "  3. Click 'New' -> 'Blueprint'"
        echo "  4. Connect your repository"
        echo "  5. Render will use render.yaml to create services"
        echo ""
        echo "Or install Render CLI: npm install -g @render/cli"
        exit 0
    fi
    
    render blueprint apply
    log_success "Render deployment initiated"
}

# Main
case "$ENVIRONMENT" in
    docker)
        check_prerequisites
        build_frontends
        deploy_docker
        ;;
    render)
        build_frontends
        deploy_render
        ;;
    build-only)
        build_frontends
        log_success "Frontend build complete"
        ;;
    *)
        echo "Unknown environment: $ENVIRONMENT"
        echo "Usage: ./scripts/deploy.sh [docker|render|build-only]"
        exit 1
        ;;
esac
