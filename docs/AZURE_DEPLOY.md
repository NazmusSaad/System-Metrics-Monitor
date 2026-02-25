# Deploy to Azure (Container Apps + Azure Postgres)

End-to-end guide to deploy the **backend** on Azure Container Apps with Azure Database for PostgreSQL (Flexible Server). The frontend stays on Vercel.

> [!NOTE]
> A fully automated script is available at [`infra/azure/deploy.ps1`](../infra/azure/deploy.ps1) (PowerShell) or [`deploy.sh`](../infra/azure/deploy.sh) (Bash). This doc explains each step for understanding and troubleshooting.

---

## Prerequisites

| Tool | Install |
|---|---|
| Azure CLI ≥ 2.53 | <https://learn.microsoft.com/cli/azure/install-azure-cli> |
| Docker Desktop | <https://www.docker.com/products/docker-desktop/> |
| Azure subscription | <https://azure.microsoft.com/free/> |

```powershell
# Verify
az version
docker --version
az login
```

---

## 1. Set Variables

Open a **PowerShell** terminal and set these variables (adjust names as needed):

```powershell
$RG       = "metrics-monitor-rg"
$LOCATION = "eastus"                          # closest region with ACA support
$ACR      = "metricsmonitoracr"               # globally unique, alphanumeric only
$PG_SVR   = "metrics-monitor-pgserver"        # globally unique
$PG_USER  = "metricsadmin"
$PG_PASS  = "Ch@ngeMe123!"                    # min 8 chars, mixed case + digits
$PG_DB    = "metrics_monitor"
$APP      = "metrics-monitor-backend"
$ACA_ENV  = "metrics-monitor-env"
$API_KEY  = "your-secret-ingest-key"          # must match agent INGEST_API_KEY
```

> [!IMPORTANT]
> Choose a **strong** `$PG_PASS`. Azure requires ≥ 8 characters with uppercase, lowercase, and digits.

---

## 2. Install CLI Extensions

```powershell
az extension add --name containerapp --upgrade -y
az provider register --namespace Microsoft.App --wait
az provider register --namespace Microsoft.OperationalInsights --wait
```

---

## 3. Create Resource Group

```powershell
az group create --name $RG --location $LOCATION
```

---

## 4. Create Azure Container Registry (ACR)

```powershell
az acr create --resource-group $RG --name $ACR --sku Basic --admin-enabled true
az acr login --name $ACR
```

---

## 5. Create Azure Database for PostgreSQL

### 5a. Create the server

```powershell
az postgres flexible-server create `
    --resource-group $RG `
    --name $PG_SVR `
    --location $LOCATION `
    --admin-user $PG_USER `
    --admin-password $PG_PASS `
    --sku-name Standard_B1ms `
    --tier Burstable `
    --storage-size 32 `
    --version 16 `
    --yes
```

> [!WARNING]
> **Cost**: `Standard_B1ms` is the cheapest tier (~$12/month). The 32 GB storage adds ~$4/month. Remember to tear down when not in use.

### 5b. Allow Azure services to connect

```powershell
az postgres flexible-server firewall-rule create `
    --resource-group $RG `
    --name $PG_SVR `
    --rule-name AllowAzureServices `
    --start-ip-address 0.0.0.0 `
    --end-ip-address 0.0.0.0
```

### 5c. Create the database

```powershell
az postgres flexible-server db create `
    --resource-group $RG `
    --server-name $PG_SVR `
    --database-name $PG_DB
```

---

## 6. Build & Push Backend Image

From the **repo root**:

```powershell
$IMAGE = "$ACR.azurecr.io/metrics-monitor-backend:latest"
docker build -t $IMAGE ./backend
docker push $IMAGE
```

---

## 7. Create Container Apps Environment

```powershell
az containerapp env create `
    --resource-group $RG `
    --name $ACA_ENV `
    --location $LOCATION
```

---

## 8. Deploy the Container App

### 8a. Build the DATABASE_URL

```powershell
$PG_HOST = "$PG_SVR.postgres.database.azure.com"
$DB_URL  = "postgresql+asyncpg://${PG_USER}:${PG_PASS}@${PG_HOST}:5432/${PG_DB}?sslmode=require"
```

> [!NOTE]
> The `?sslmode=require` param is required. The backend code detects it and configures SSL for both asyncpg and Alembic migrations automatically.

### 8b. Get ACR password

```powershell
$ACR_PASS = (az acr credential show --name $ACR --query "passwords[0].value" -o tsv)
```

### 8c. Create the app

```powershell
az containerapp create `
    --resource-group $RG `
    --name $APP `
    --environment $ACA_ENV `
    --image $IMAGE `
    --registry-server "$ACR.azurecr.io" `
    --registry-username $ACR `
    --registry-password $ACR_PASS `
    --target-port 8000 `
    --ingress external `
    --min-replicas 1 `
    --max-replicas 1 `
    --cpu 0.5 `
    --memory 1.0Gi `
    --env-vars `
        "DATABASE_URL=$DB_URL" `
        "INGEST_API_KEY=$API_KEY" `
        "ENABLE_LOCAL_COLLECTOR=false" `
        "MACHINE_NAME=azure" `
        "CPU_WARN=80" `
        "CPU_CRIT=95" `
        "MEM_WARN=80" `
        "MEM_CRIT=95" `
        "DISK_WARN=85" `
        "DISK_CRIT=95"
```

> [!NOTE]
> **Replicas = 1**: Alembic runs migrations on every container start. With 1 replica there are no race conditions. If you scale up later, run migrations as a one-off [Container App Job](https://learn.microsoft.com/azure/container-apps/jobs) first, then remove `alembic upgrade head` from the Dockerfile CMD.

---

## 9. Get the Backend URL

```powershell
$FQDN = (az containerapp show --resource-group $RG --name $APP --query "properties.configuration.ingress.fqdn" -o tsv)
$BACKEND_URL = "https://$FQDN"
Write-Host "Backend URL: $BACKEND_URL"
```

---

## 10. Test Endpoints

```powershell
# Health check
Invoke-RestMethod "$BACKEND_URL/api/health"

# List hosts
Invoke-RestMethod "$BACKEND_URL/api/hosts"

# Test ingest
$body = @{
    host_key       = "test-device"
    ts_utc         = (Get-Date -Format "o")
    cpu_percent    = 42.5
    mem_used_bytes = 4000000000
    mem_total_bytes= 8000000000
    mem_percent    = 50.0
    disk_used_bytes= 100000000000
    disk_total_bytes=500000000000
    disk_percent   = 20.0
    net_rx_bps     = 1000.0
    net_tx_bps     = 500.0
} | ConvertTo-Json

Invoke-RestMethod -Uri "$BACKEND_URL/api/ingest" `
    -Method POST `
    -Headers @{ "X-API-KEY" = $API_KEY; "Content-Type" = "application/json" } `
    -Body $body
```

---

## 11. Connect the Agent

On each remote machine, set `BACKEND_URL` to your new Azure URL:

```bash
docker run -d --name metrics-agent --pid=host \
  -e BACKEND_URL=https://<your-app>.azurecontainerapps.io \
  -e INGEST_API_KEY=your-secret-ingest-key \
  -e HOST_KEY=my-server-1 \
  metrics-agent
```

---

## 12. Connect the Vercel Frontend

In Vercel project settings → Environment Variables, update:

```
VITE_API_URL=https://<your-app>.azurecontainerapps.io
```

Redeploy the frontend for the change to take effect.

---

## 13. Update Environment Variables (After Deployment)

To change env vars on the running container app:

```powershell
az containerapp update `
    --resource-group $RG `
    --name $APP `
    --set-env-vars "INGEST_API_KEY=new-secret-key"
```

---

## 14. View Logs

```powershell
az containerapp logs show `
    --resource-group $RG `
    --name $APP `
    --type console `
    --follow
```

---

## 15. Redeploy After Code Changes

```powershell
# Rebuild and push
docker build -t $IMAGE ./backend
docker push $IMAGE

# Update the container app to pull the new image
az containerapp update `
    --resource-group $RG `
    --name $APP `
    --image $IMAGE
```

---

## 16. Restrict CORS (Production)

The backend currently allows all origins (`allow_origins=["*"]`). To restrict:

1. Edit `backend/app/main.py` and set `allow_origins` to your Vercel domain:
   ```python
   allow_origins=["https://your-app.vercel.app"]
   ```
2. Rebuild and redeploy (step 15).

---

## Cleanup

Delete **everything** (ACR, PostgreSQL, Container App, environment):

```powershell
az group delete --name $RG --yes --no-wait
```

Or use the provided teardown script:

```powershell
.\infra\azure\teardown.ps1 -ResourceGroup $RG
```

---

## Troubleshooting

| Symptom | Likely Cause | Fix |
|---|---|---|
| Container stuck in "Provisioning" | IMAGE pull failure | Verify ACR login: `az acr login --name $ACR` and image exists: `az acr repository list --name $ACR` |
| `SSL SYSCALL error` or connection refused | Missing `?sslmode=require` in DATABASE_URL | Ensure `DATABASE_URL` ends with `?sslmode=require` |
| Alembic migration error | DATABASE_URL wrong, or DB not created | Verify DB exists: `az postgres flexible-server db list --resource-group $RG --server-name $PG_SVR` |
| 401 on `/api/ingest` | `INGEST_API_KEY` mismatch | Check env var on container app and agent match |
| CORS errors from frontend | `allow_origins` too restrictive | Set `allow_origins=["*"]` or add your Vercel domain |
| Container restarts repeatedly | Check logs | `az containerapp logs show --name $APP --resource-group $RG --type console` |
| Firewall blocking Postgres | Missing firewall rule | Re-run step 5b (AllowAzureServices firewall rule) |
| `Name already in use` errors | ACR/PG names must be globally unique | Change `$ACR` or `$PG_SVR` to a unique name |

---

## Cost Estimate (Monthly)

| Resource | SKU | Estimated Cost |
|---|---|---|
| Azure Container Registry | Basic | ~$5 |
| Azure Database for PostgreSQL | Standard_B1ms + 32 GB | ~$16 |
| Container Apps | 0.5 vCPU / 1 GiB, 1 replica | ~$20–36 (free tier may apply) |
| **Total** | | **~$41–57/month** |

> [!TIP]
> ACA has a generous free grant (180,000 vCPU-seconds and 360,000 GiB-seconds per subscription per month). A single 0.5-CPU replica running 24/7 uses ~1.3M vCPU-seconds, so you'll exceed the free tier. Set `--min-replicas 0` to scale to zero when idle and save costs.
