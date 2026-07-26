# Delayed full mapping-pipeline runner.
# The initial wait lets a separate high-memory workflow finish before the
# mapping stages load the full all-economy source tables.

$ErrorActionPreference = "Stop"
$repo = "C:\Users\Work\github\leap_mappings"
$python = "C:\Users\Work\miniconda3\python.exe"
$log = Join-Path $repo "results\logs\mapping_pipeline_delayed_$(Get-Date -Format yyyyMMdd_HHmmss).log"
$logParent = Split-Path -Parent $log
New-Item -ItemType Directory -Force -Path $logParent | Out-Null

Write-Output "Delayed mapping pipeline started at $(Get-Date -Format o)"
Write-Output "Waiting three hours before loading mapping inputs..."
Start-Sleep -Seconds 10800

Set-Location $repo
Write-Output "Starting full mapping pipeline at $(Get-Date -Format o)"
& $python codebase\run_mapping_pipeline.py `
    --stages 1,2,data_convert,3 `
    --skip leap_parse `
    --esto-path data\00APEC_2025_low_with_subtotals.csv `
    --esto-extended-path data\esto_extended.csv `
    --mapping-workbook-path config\outlook_mappings_master_combined_esto.xlsx `
    --ninth-path data\merged_file_energy_ALL_20251106.csv `
    --raw-leap-path results\mapping_relationships\raw_leap_results.csv `
    *>&1 | Tee-Object -FilePath $log

exit $LASTEXITCODE
