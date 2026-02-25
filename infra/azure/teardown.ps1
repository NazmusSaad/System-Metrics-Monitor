<#
.SYNOPSIS
    Delete all Azure resources created by deploy.ps1.
.DESCRIPTION
    Deletes the entire resource group, which removes ACR, PostgreSQL, and Container App.
.PARAMETER ResourceGroup
    Name of the resource group to delete (default: metrics-monitor-rg)
#>

param(
    [string]$ResourceGroup = "metrics-monitor-rg"
)

Write-Host "`n=== Metrics Monitor — Azure Teardown ===" -ForegroundColor Red
Write-Host "This will DELETE resource group '$ResourceGroup' and ALL resources inside it.`n" -ForegroundColor Red

$confirm = Read-Host "Type the resource group name to confirm"
if ($confirm -ne $ResourceGroup) {
    Write-Host "Aborted. Name did not match." -ForegroundColor Yellow
    exit 1
}

Write-Host "Deleting resource group '$ResourceGroup'..." -ForegroundColor Yellow
az group delete --name $ResourceGroup --yes --no-wait

Write-Host "`nDeletion initiated (runs in background). It may take a few minutes." -ForegroundColor Green
Write-Host "Verify with: az group show --name $ResourceGroup" -ForegroundColor Gray
