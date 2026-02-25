#!/usr/bin/env bash
#
# Deploy Metrics Monitor backend to Azure Container Apps + Azure Database for PostgreSQL.
# Idempotent — safe to re-run; existing resources are skipped.
#
# Prerequisites: Azure CLI (az), Docker, logged in (az login).
#
# Usage:
#   chmod +x deploy.sh
#   ./deploy.sh                          # uses defaults
#   ./deploy.sh -g my-rg -l westus2     # override resource group & location
#
set -euo pipefail

# ── Defaults ──────────────────────────────────────────────────────
RESOURCE_GROUP="metrics-monitor-rg"
LOCATION="eastus"
ACR_NAME="metricsmonitoracr"
PG_SERVER="metrics-monitor-pgserver"
PG_USER="metricsadmin"
PG_PASSWORD=""
PG_DB="metrics_monitor"
APP_NAME="metrics-monitor-backend"
ACA_ENV="metrics-monitor-env"
INGEST_API_KEY="changeme-secret-key"

# ── Parse args ────────────────────────────────────────────────────
while getopts "g:l:a:s:u:p:d:n:k:" opt; do
    case $opt in
        g) RESOURCE_GROUP="$OPTARG" ;;
        l) LOCATION="$OPTARG" ;;
        a) ACR_NAME="$OPTARG" ;;
        s) PG_SERVER="$OPTARG" ;;
        u) PG_USER="$OPTARG" ;;
        p) PG_PASSWORD="$OPTARG" ;;
        d) PG_DB="$OPTARG" ;;
        n) APP_NAME="$OPTARG" ;;
        k) INGEST_API_KEY="$OPTARG" ;;
        *) echo "Unknown option -$opt"; exit 1 ;;
    esac
done

if [ -z "$PG_PASSWORD" ]; then
    read -sp "Enter PostgreSQL admin password (min 8 chars, mixed case + digits): " PG_PASSWORD
    echo
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="$SCRIPT_DIR/../../backend"

echo ""
echo "=== Metrics Monitor — Azure Deployment ==="
echo "Resource Group : $RESOURCE_GROUP"
echo "Location       : $LOCATION"
echo "ACR            : $ACR_NAME"
echo "Postgres Server: $PG_SERVER"
echo "Container App  : $APP_NAME"
echo ""

# ── 0. CLI extensions ──────────────────────────────────────────────
echo "[0/7] Installing Azure CLI extensions..."
az extension add --name containerapp --upgrade -y 2>/dev/null || true
az provider register --namespace Microsoft.App --wait 2>/dev/null || true
az provider register --namespace Microsoft.OperationalInsights --wait 2>/dev/null || true

# ── 1. Resource Group ──────────────────────────────────────────────
echo "[1/7] Creating resource group..."
az group create --name "$RESOURCE_GROUP" --location "$LOCATION" --output none

# ── 2. Azure Container Registry ───────────────────────────────────
echo "[2/7] Creating Azure Container Registry..."
az acr create --resource-group "$RESOURCE_GROUP" --name "$ACR_NAME" --sku Basic --admin-enabled true --output none 2>/dev/null || true
az acr login --name "$ACR_NAME"

# ── 3. PostgreSQL Flexible Server ─────────────────────────────────
echo "[3/7] Creating PostgreSQL Flexible Server (Standard_B1ms)..."
az postgres flexible-server create \
    --resource-group "$RESOURCE_GROUP" \
    --name "$PG_SERVER" \
    --location "$LOCATION" \
    --admin-user "$PG_USER" \
    --admin-password "$PG_PASSWORD" \
    --sku-name Standard_B1ms \
    --tier Burstable \
    --storage-size 32 \
    --version 16 \
    --yes \
    --output none 2>/dev/null || true

echo "     Configuring firewall (allow Azure services)..."
az postgres flexible-server firewall-rule create \
    --resource-group "$RESOURCE_GROUP" \
    --name "$PG_SERVER" \
    --rule-name AllowAzureServices \
    --start-ip-address 0.0.0.0 \
    --end-ip-address 0.0.0.0 \
    --output none 2>/dev/null || true

echo "     Creating database '$PG_DB'..."
az postgres flexible-server db create \
    --resource-group "$RESOURCE_GROUP" \
    --server-name "$PG_SERVER" \
    --database-name "$PG_DB" \
    --output none 2>/dev/null || true

# ── 4. Build and push Docker image ────────────────────────────────
echo "[4/7] Building and pushing backend image to ACR..."
IMAGE_TAG="$ACR_NAME.azurecr.io/metrics-monitor-backend:latest"
docker build -t "$IMAGE_TAG" "$BACKEND_DIR"
docker push "$IMAGE_TAG"

# ── 5. Container Apps Environment ─────────────────────────────────
echo "[5/7] Creating Container Apps environment..."
az containerapp env create \
    --resource-group "$RESOURCE_GROUP" \
    --name "$ACA_ENV" \
    --location "$LOCATION" \
    --output none 2>/dev/null || true

# ── 6. DATABASE_URL ───────────────────────────────────────────────
PG_HOST="$PG_SERVER.postgres.database.azure.com"
DATABASE_URL="postgresql+asyncpg://${PG_USER}:${PG_PASSWORD}@${PG_HOST}:5432/${PG_DB}?sslmode=require"

# ── 7. Container App ──────────────────────────────────────────────
echo "[6/7] Creating Container App..."
ACR_PASSWORD=$(az acr credential show --name "$ACR_NAME" --query "passwords[0].value" -o tsv)

az containerapp create \
    --resource-group "$RESOURCE_GROUP" \
    --name "$APP_NAME" \
    --environment "$ACA_ENV" \
    --image "$IMAGE_TAG" \
    --registry-server "$ACR_NAME.azurecr.io" \
    --registry-username "$ACR_NAME" \
    --registry-password "$ACR_PASSWORD" \
    --target-port 8000 \
    --ingress external \
    --min-replicas 1 \
    --max-replicas 1 \
    --cpu 0.5 \
    --memory 1.0Gi \
    --env-vars \
        "DATABASE_URL=$DATABASE_URL" \
        "INGEST_API_KEY=$INGEST_API_KEY" \
        "ENABLE_LOCAL_COLLECTOR=false" \
        "MACHINE_NAME=azure" \
        "CPU_WARN=80" \
        "CPU_CRIT=95" \
        "MEM_WARN=80" \
        "MEM_CRIT=95" \
        "DISK_WARN=85" \
        "DISK_CRIT=95" \
    --output none

# ── Done ──────────────────────────────────────────────────────────
echo "[7/7] Retrieving backend URL..."
FQDN=$(az containerapp show --resource-group "$RESOURCE_GROUP" --name "$APP_NAME" --query "properties.configuration.ingress.fqdn" -o tsv)
BACKEND_URL="https://$FQDN"

echo ""
echo "===================================================="
echo " Deployment complete!"
echo "===================================================="
echo "Backend URL : $BACKEND_URL"
echo "Health check: $BACKEND_URL/api/health"
echo ""
echo "Next steps:"
echo "  1. Test:   curl $BACKEND_URL/api/health"
echo "  2. Update agents:  BACKEND_URL=$BACKEND_URL"
echo "  3. Update Vercel:  VITE_API_URL=$BACKEND_URL"
echo "  4. Cleanup:        ./teardown.sh -g $RESOURCE_GROUP"
