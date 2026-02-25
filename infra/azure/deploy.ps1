<#
.SYNOPSIS
    Deploy Metrics Monitor backend to Azure Container Apps + Azure Database for PostgreSQL.
.DESCRIPTION
    Idempotent deployment script. Safe to re-run — existing resources are skipped.
    Prerequisites: Azure CLI (az), Docker Desktop running, logged in to Azure (az login).
.PARAMETER ResourceGroup
    Name of the Azure resource group (default: metrics-monitor-rg)
.PARAMETER Location
    Azure region (default: eastus)
.PARAMETER AcrName
    Azure Container Registry name — must be globally unique, alphanumeric only (default: metricsmonitoracr)
.PARAMETER PostgresServerName
    PostgreSQL Flexible Server name — must be globally unique (default: metrics-monitor-pgserver)
.PARAMETER PostgresUser
    PostgreSQL admin username (default: metricsadmin)
.PARAMETER PostgresPassword
    PostgreSQL admin password (default: prompted interactively)
.PARAMETER PostgresDb
    Database name (default: metrics_monitor)
.PARAMETER AppName
    Container App name (default: metrics-monitor-backend)
.PARAMETER IngestApiKey
    API key for agent ingest auth (default: changeme-secret-key)
#>

param(
    [string]$ResourceGroup   = "metrics-monitor-rg",
    [string]$Location        = "eastus",
    [string]$AcrName         = "metricsmonitoracr",
    [string]$PostgresServerName = "metrics-monitor-pgserver",
    [string]$PostgresUser    = "metricsadmin",
    [string]$PostgresPassword = "",
    [string]$PostgresDb      = "metrics_monitor",
    [string]$AppName         = "metrics-monitor-backend",
    [string]$AcaEnvName      = "metrics-monitor-env",
    [string]$IngestApiKey    = "changeme-secret-key"
)

$ErrorActionPreference = "Stop"

# ──────────────────────────────────────────────────────────────────
# Prompt for password if not provided
# ──────────────────────────────────────────────────────────────────
if (-not $PostgresPassword) {
    $securePass = Read-Host "Enter PostgreSQL admin password (min 8 chars, mixed case + digits)" -AsSecureString
    $PostgresPassword = [Runtime.InteropServices.Marshal]::PtrToStringAuto(
        [Runtime.InteropServices.Marshal]::SecureStringToBSTR($securePass))
}

Write-Host "`n=== Metrics Monitor — Azure Deployment ===" -ForegroundColor Cyan
Write-Host "Resource Group : $ResourceGroup"
Write-Host "Location       : $Location"
Write-Host "ACR            : $AcrName"
Write-Host "Postgres Server: $PostgresServerName"
Write-Host "Container App  : $AppName`n"

# ──────────────────────────────────────────────────────────────────
# 0. Ensure required CLI extensions
# ──────────────────────────────────────────────────────────────────
Write-Host "[0/7] Installing Azure CLI extensions..." -ForegroundColor Yellow
az extension add --name containerapp --upgrade -y 2>$null
az provider register --namespace Microsoft.App --wait 2>$null
az provider register --namespace Microsoft.OperationalInsights --wait 2>$null

# ──────────────────────────────────────────────────────────────────
# 1. Resource Group
# ──────────────────────────────────────────────────────────────────
Write-Host "[1/7] Creating resource group..." -ForegroundColor Yellow
az group create --name $ResourceGroup --location $Location --output none

# ──────────────────────────────────────────────────────────────────
# 2. Azure Container Registry
# ──────────────────────────────────────────────────────────────────
Write-Host "[2/7] Creating Azure Container Registry..." -ForegroundColor Yellow
az acr create --resource-group $ResourceGroup --name $AcrName --sku Basic --admin-enabled true --output none 2>$null
az acr login --name $AcrName

# ──────────────────────────────────────────────────────────────────
# 3. Azure Database for PostgreSQL — Flexible Server
# ──────────────────────────────────────────────────────────────────
Write-Host "[3/7] Creating PostgreSQL Flexible Server (Standard_B1ms)..." -ForegroundColor Yellow
az postgres flexible-server create `
    --resource-group $ResourceGroup `
    --name $PostgresServerName `
    --location $Location `
    --admin-user $PostgresUser `
    --admin-password $PostgresPassword `
    --sku-name Standard_B1ms `
    --tier Burstable `
    --storage-size 32 `
    --version 16 `
    --yes `
    --output none 2>$null

# Allow Azure services to connect
Write-Host "     Configuring firewall (allow Azure services)..." -ForegroundColor Gray
az postgres flexible-server firewall-rule create `
    --resource-group $ResourceGroup `
    --name $PostgresServerName `
    --rule-name AllowAzureServices `
    --start-ip-address 0.0.0.0 `
    --end-ip-address 0.0.0.0 `
    --output none 2>$null

# Create the database
Write-Host "     Creating database '$PostgresDb'..." -ForegroundColor Gray
az postgres flexible-server db create `
    --resource-group $ResourceGroup `
    --server-name $PostgresServerName `
    --database-name $PostgresDb `
    --output none 2>$null

# ──────────────────────────────────────────────────────────────────
# 4. Build and push Docker image
# ──────────────────────────────────────────────────────────────────
Write-Host "[4/7] Building and pushing backend image to ACR..." -ForegroundColor Yellow
$repoRoot = Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $PSScriptRoot))
# If the script is at infra/azure/deploy.ps1, go up 2 to get repo root
$backendDir = Join-Path $PSScriptRoot "..\..\backend" | Resolve-Path
$imageTag = "$AcrName.azurecr.io/metrics-monitor-backend:latest"

docker build -t $imageTag $backendDir
docker push $imageTag

# ──────────────────────────────────────────────────────────────────
# 5. Container Apps Environment
# ──────────────────────────────────────────────────────────────────
Write-Host "[5/7] Creating Container Apps environment..." -ForegroundColor Yellow
az containerapp env create `
    --resource-group $ResourceGroup `
    --name $AcaEnvName `
    --location $Location `
    --output none 2>$null

# ──────────────────────────────────────────────────────────────────
# 6. Build DATABASE_URL
# ──────────────────────────────────────────────────────────────────
$pgHost = "$PostgresServerName.postgres.database.azure.com"
$databaseUrl = "postgresql+asyncpg://${PostgresUser}:${PostgresPassword}@${pgHost}:5432/${PostgresDb}?sslmode=require"

# ──────────────────────────────────────────────────────────────────
# 7. Create / update Container App
# ──────────────────────────────────────────────────────────────────
Write-Host "[6/7] Creating Container App..." -ForegroundColor Yellow

# Get ACR credentials
$acrPassword = (az acr credential show --name $AcrName --query "passwords[0].value" -o tsv)

az containerapp create `
    --resource-group $ResourceGroup `
    --name $AppName `
    --environment $AcaEnvName `
    --image $imageTag `
    --registry-server "$AcrName.azurecr.io" `
    --registry-username $AcrName `
    --registry-password $acrPassword `
    --target-port 8000 `
    --ingress external `
    --min-replicas 1 `
    --max-replicas 1 `
    --cpu 0.5 `
    --memory 1.0Gi `
    --env-vars `
        "DATABASE_URL=$databaseUrl" `
        "INGEST_API_KEY=$IngestApiKey" `
        "ENABLE_LOCAL_COLLECTOR=false" `
        "MACHINE_NAME=azure" `
        "CPU_WARN=80" `
        "CPU_CRIT=95" `
        "MEM_WARN=80" `
        "MEM_CRIT=95" `
        "DISK_WARN=85" `
        "DISK_CRIT=95" `
    --output none

# ──────────────────────────────────────────────────────────────────
# Done — print the URL
# ──────────────────────────────────────────────────────────────────
Write-Host "[7/7] Retrieving backend URL..." -ForegroundColor Yellow
$fqdn = (az containerapp show --resource-group $ResourceGroup --name $AppName --query "properties.configuration.ingress.fqdn" -o tsv)
$backendUrl = "https://$fqdn"

Write-Host "`n====================================================" -ForegroundColor Green
Write-Host " Deployment complete!" -ForegroundColor Green
Write-Host "====================================================" -ForegroundColor Green
Write-Host "Backend URL : $backendUrl"
Write-Host "Health check: $backendUrl/api/health"
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "  1. Test:   curl $backendUrl/api/health"
Write-Host "  2. Update agents:  BACKEND_URL=$backendUrl"
Write-Host "  3. Update Vercel:  VITE_API_URL=$backendUrl"
Write-Host "  4. Cleanup:        .\teardown.ps1 -ResourceGroup $ResourceGroup"
