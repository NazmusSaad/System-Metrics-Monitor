#!/usr/bin/env bash
#
# Delete all Azure resources created by deploy.sh.
# Deletes the entire resource group (ACR, PostgreSQL, Container App).
#
# Usage:
#   ./teardown.sh                        # default: metrics-monitor-rg
#   ./teardown.sh -g my-custom-rg
#
set -euo pipefail

RESOURCE_GROUP="metrics-monitor-rg"

while getopts "g:" opt; do
    case $opt in
        g) RESOURCE_GROUP="$OPTARG" ;;
        *) echo "Unknown option -$opt"; exit 1 ;;
    esac
done

echo ""
echo "=== Metrics Monitor — Azure Teardown ==="
echo "This will DELETE resource group '$RESOURCE_GROUP' and ALL resources inside it."
echo ""
read -rp "Type the resource group name to confirm: " CONFIRM

if [ "$CONFIRM" != "$RESOURCE_GROUP" ]; then
    echo "Aborted. Name did not match."
    exit 1
fi

echo "Deleting resource group '$RESOURCE_GROUP'..."
az group delete --name "$RESOURCE_GROUP" --yes --no-wait

echo ""
echo "Deletion initiated (runs in background). It may take a few minutes."
echo "Verify with: az group show --name $RESOURCE_GROUP"
