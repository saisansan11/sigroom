[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^[0-9a-f]{40}$')]
    [string]$CommitSha,

    [switch]$Deploy,

    [string]$ConfirmProduction = "",

    [string]$Project = "sixth-storm-439008-u2",
    [string]$Region = "asia-southeast3",
    [string]$Service = "sigroom",
    [string]$Configuration = "sigroom"
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$ExpectedProject = "sixth-storm-439008-u2"
$ExpectedRegion = "asia-southeast3"
$ExpectedService = "sigroom"
$ExpectedConfiguration = "sigroom"
$ExpectedTrigger = "auto-deploy-sigroom"

function Invoke-Checked {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Executable,
        [Parameter(Mandatory = $true)]
        [string[]]$Arguments
    )

    & $Executable @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "$Executable failed with exit code $LASTEXITCODE"
    }
}

function Get-CheckedOutput {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Executable,
        [Parameter(Mandatory = $true)]
        [string[]]$Arguments
    )

    $output = & $Executable @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "$Executable failed with exit code $LASTEXITCODE"
    }
    return ($output | Out-String).Trim()
}

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Push-Location $repoRoot
try {
    $headSha = Get-CheckedOutput -Executable "git" -Arguments @("rev-parse", "HEAD")
    $dirtyWorktree = Get-CheckedOutput -Executable "git" -Arguments @("status", "--porcelain")
    if ($dirtyWorktree) {
        throw "BLOCKED: worktree is not clean. Commit/review all non-ignored tracked and untracked files before any production deploy."
    }

    Invoke-Checked -Executable "python" -Arguments @(
        (Join-Path $PSScriptRoot "sigroom_deploy_guard.py"),
        "--project", $Project,
        "--region", $Region,
        "--service", $Service,
        "--configuration", $Configuration,
        "--commit-sha", $CommitSha,
        "--head-sha", $headSha
    )

    $configProject = Get-CheckedOutput -Executable "gcloud" -Arguments @(
        "config", "get-value", "project", "--configuration=$ExpectedConfiguration"
    )
    if ($configProject -ne $ExpectedProject) {
        throw "BLOCKED: gcloud configuration '$ExpectedConfiguration' points to '$configProject', expected '$ExpectedProject'."
    }

    $configRegion = Get-CheckedOutput -Executable "gcloud" -Arguments @(
        "config", "get-value", "run/region", "--configuration=$ExpectedConfiguration"
    )
    if ($configRegion -ne $ExpectedRegion) {
        throw "BLOCKED: gcloud configuration '$ExpectedConfiguration' region is '$configRegion', expected '$ExpectedRegion'."
    }

    $triggerDisabled = Get-CheckedOutput -Executable "gcloud" -Arguments @(
        "builds", "triggers", "describe", $ExpectedTrigger,
        "--project=$ExpectedProject",
        "--configuration=$ExpectedConfiguration",
        "--format=value(disabled)"
    )
    if ($triggerDisabled -ne "True") {
        throw "BLOCKED: $ExpectedTrigger must remain disabled before a manual production release."
    }

    $serviceName = Get-CheckedOutput -Executable "gcloud" -Arguments @(
        "run", "services", "describe", $ExpectedService,
        "--region=$ExpectedRegion",
        "--project=$ExpectedProject",
        "--configuration=$ExpectedConfiguration",
        "--format=value(metadata.name)"
    )
    if ($serviceName -ne $ExpectedService) {
        throw "BLOCKED: Cloud Run service verification returned '$serviceName', expected '$ExpectedService'."
    }

    Write-Host "PREFLIGHT PASS: SIGROOM production target is fail-closed and exact." -ForegroundColor Green
    Write-Host "  configuration: $ExpectedConfiguration"
    Write-Host "  project:       $ExpectedProject"
    Write-Host "  region:        $ExpectedRegion"
    Write-Host "  service:       $ExpectedService"
    Write-Host "  commit:        $CommitSha"
    Write-Host "  auto deploy:   disabled"

    if (-not $Deploy) {
        Write-Host "CHECK-ONLY: no build, migration, traffic, or production write was started." -ForegroundColor Cyan
        exit 0
    }

    if ($ConfirmProduction -ne "DEPLOY") {
        throw "BLOCKED: production deploy requires -ConfirmProduction DEPLOY."
    }

    Write-Host "Starting manual SIGROOM production release for exact SHA $CommitSha" -ForegroundColor Yellow
    Invoke-Checked -Executable "gcloud" -Arguments @(
        "builds", "submit", ".",
        "--config=cloudbuild.yaml",
        "--substitutions=COMMIT_SHA=$CommitSha",
        "--project=$ExpectedProject",
        "--configuration=$ExpectedConfiguration",
        "--quiet"
    )
}
finally {
    Pop-Location
}
