#!/usr/bin/env bash
# Deploy Marketing Intelligence to Databricks Apps using Databricks Asset Bundles (DABs)
set -euo pipefail

WAREHOUSE_ID="${1:-}"
GENIE_SPACE_ID="${2:-}"
APP_NAME="${3:-marketing-intelligence}"
PROFILE="${4:-DEFAULT}"
VALIDATE_ONLY="${5:-false}"

if [ -z "$WAREHOUSE_ID" ] || [ -z "$GENIE_SPACE_ID" ]; then
    echo "Usage: ./deploy.sh <WAREHOUSE_ID> <GENIE_SPACE_ID> [APP_NAME] [PROFILE] [VALIDATE_ONLY: true|false]"
    echo "Example: ./deploy.sh abcd1234efgh5678 01ef-space-id marketing-intelligence DEFAULT false"
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

export BUNDLE_VAR_warehouse_id="$WAREHOUSE_ID"
export BUNDLE_VAR_genie_space_id="$GENIE_SPACE_ID"
export BUNDLE_VAR_app_name="$APP_NAME"

echo "Validating Databricks bundle..."
databricks bundle validate --profile "$PROFILE"

if [ "$VALIDATE_ONLY" = "true" ]; then
    echo "Validation successful. Exiting as validate-only was requested."
    exit 0
fi

echo "Deploying Databricks app bundle..."
databricks bundle deploy --profile "$PROFILE"

echo "Starting Databricks app..."
databricks bundle run marketing --profile "$PROFILE"

echo "Databricks app deployed and running successfully."
