param(
    [string]$OrcaRoot = "D:\ORCA"
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path $OrcaRoot)) {
    throw "ORCA workspace not found: $OrcaRoot"
}

$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$backupRoot = Join-Path $OrcaRoot ".agents\backups\$stamp"
New-Item -ItemType Directory -Force -Path $backupRoot | Out-Null

$extensionFile = Join-Path $OrcaRoot ".vscode\extensions.json"
if (Test-Path $extensionFile) {
    Copy-Item $extensionFile (Join-Path $backupRoot "extensions.json") -Force
}

$sourceVscode = Join-Path $PSScriptRoot ".vscode\extensions.json"
$sourceAgents = Join-Path $PSScriptRoot ".agents"
$targetVscode = Join-Path $OrcaRoot ".vscode"
$targetAgents = Join-Path $OrcaRoot ".agents"

New-Item -ItemType Directory -Force -Path $targetVscode | Out-Null
New-Item -ItemType Directory -Force -Path $targetAgents | Out-Null

Copy-Item $sourceVscode $targetVscode -Force
Copy-Item (Join-Path $sourceAgents "rules") (Join-Path $targetAgents "rules") -Recurse -Force
Copy-Item (Join-Path $sourceAgents "skills") (Join-Path $targetAgents "skills") -Recurse -Force

Write-Host ""
Write-Host "ORCA workstation baseline applied." -ForegroundColor Green
Write-Host "Backup: $backupRoot"
Write-Host ""
Write-Host "Next: open the workspace in Antigravity and run the execution directive in APPLY_IN_ANTIGRAVITY.md."
