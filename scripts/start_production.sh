#!/usr/bin/env bash
# Production Start Script for RasoSynthTune Cluster
set -eo pipefail

echo "=========================================================="
echo " Starting RasoSynthTune Production Cluster Stack"
echo "=========================================================="

# 1. Check docker and docker compose
if ! command -v docker &> /dev/null; then
    echo "ERROR: Docker is not installed or not in PATH."
    exit 1
fi

# 2. Check or create .env.production
if [ ! -f .env.production ] && [ ! -f .env ]; then
    echo "Creating .env.production from defaults..."
    cat <<EOF > .env.production
ENVIRONMENT=production
POSTGRES_DB=rasosynthtune
POSTGRES_USER=raso_admin
POSTGRES_PASSWORD=$(openssl rand -hex 16 2>/dev/null || echo "prod_db_secret_key_12345")
JWT_SECRET=$(openssl rand -hex 32 2>/dev/null || echo "super-secret-production-rasosynth-jwt-key-2026")
DOWNLOAD_SIGNING_SECRET=$(openssl rand -hex 32 2>/dev/null || echo "production-signing-secret-key-32chars")
MINIO_ROOT_USER=raso_minio_admin
MINIO_ROOT_PASSWORD=$(openssl rand -hex 16 2>/dev/null || echo "prod_minio_secret_key_12345")
EOF
fi

# 3. Create required persistent local directories
mkdir -p outputs/finetune data/cache data/minio

# 4. Pull and build containers
echo "Starting multi-container topology via docker-compose.prod.yml..."
docker compose -f docker-compose.prod.yml up -d --build

# 5. Wait for healthy API
echo "Waiting for backend API healthcheck to become healthy..."
MAX_RETRIES=30
RETRY_COUNT=0
HEALTH_URL="http://localhost:8000/health"

until curl -sf "$HEALTH_URL" > /dev/null 2>&1 || [ $RETRY_COUNT -eq $MAX_RETRIES ]; do
    RETRY_COUNT=$((RETRY_COUNT+1))
    echo "  [Retry $RETRY_COUNT/$MAX_RETRIES] API initializing..."
    sleep 3
done

if [ $RETRY_COUNT -eq $MAX_RETRIES ]; then
    echo "ERROR: RasoSynthTune API failed to become healthy within expected window."
    docker compose -f docker-compose.prod.yml logs --tail 50 api
    exit 1
fi

echo "=========================================================="
echo " RasoSynthTune Cluster Successfully Initialized & Live"
echo "  - Frontend UI Dashboard : http://localhost:3000"
echo "  - Backend API & OpenAPI : http://localhost:8000/docs"
echo "  - MinIO Storage Console : http://localhost:9001"
echo "=========================================================="
