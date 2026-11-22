param(
    [Parameter(Mandatory=$true)][ValidatePattern('^[A-Za-z0-9-]+$')][string]$WarehouseId,
    [Parameter(Mandatory=$true)][ValidatePattern('^[A-Za-z0-9-]+$')][string]$GenieSpaceId,
    [ValidatePattern('^[a-z][a-z0-9-]+$')][string]$AppName = 'marketing-intelligence',
    [string]$Profile = 'DEFAULT',
    [switch]$ValidateOnly
)
$ErrorActionPreference = 'Stop'
Push-Location -LiteralPath $PSScriptRoot
$priorWarehouse = $env:BUNDLE_VAR_warehouse_id
$priorGenie = $env:BUNDLE_VAR_genie_space_id
$priorApp = $env:BUNDLE_VAR_app_name
try {
    $env:BUNDLE_VAR_warehouse_id = $WarehouseId
    $env:BUNDLE_VAR_genie_space_id = $GenieSpaceId
    $env:BUNDLE_VAR_app_name = $AppName
    & databricks bundle validate --profile $Profile
    if ($LASTEXITCODE -ne 0) { throw 'Bundle validation failed. No deployment was started.' }
    if ($ValidateOnly) { return }
    & databricks bundle deploy --profile $Profile
    if ($LASTEXITCODE -ne 0) { throw 'Bundle deployment failed. Inspect the Databricks CLI output.' }
    & databricks bundle run marketing --profile $Profile
    if ($LASTEXITCODE -ne 0) { throw 'App startup failed. Inspect its Databricks deployment logs.' }
} finally {
    $env:BUNDLE_VAR_warehouse_id = $priorWarehouse
    $env:BUNDLE_VAR_genie_space_id = $priorGenie
    $env:BUNDLE_VAR_app_name = $priorApp
    Pop-Location
}
