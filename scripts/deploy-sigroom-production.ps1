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
# ค่าคงที่ (ไม่รับเป็น parameter เพื่อกันชี้ผิดเป้าหมาย): site ใน firebase.json และ URL สำหรับตรวจหลัง deploy
$FirebaseSite = "sigroom"
$PublicUrl = "https://sigroom.web.app"

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
    Write-Host "OK: Cloud Build (build, migrate, deploy Cloud Run) เสร็จเรียบร้อย" -ForegroundColor Green

    # --- ส่วนที่ 2: อัปโหลด public/ (หน้า splash + ไฟล์ static) ขึ้น Firebase Hosting ---
    # ทำหลัง Cloud Build สำเร็จเท่านั้น (worktree สะอาดและตรง SHA เดียวกับ image แล้ว จึงได้ไฟล์ static ชุดเดียวกัน)
    Write-Host "กำลังรวมไฟล์ static (collectstatic) ให้ตรงกับเวอร์ชันที่เพิ่ง deploy..." -ForegroundColor Yellow
    $previousSecret = $env:DJANGO_SECRET_KEY
    $env:DJANGO_SECRET_KEY = "dummy-for-build"   # เหมือนใน Dockerfile; ใช้เฉพาะ process นี้ ไม่แตะฐานข้อมูล
    try {
        Invoke-Checked -Executable "uv" -Arguments @("run", "python", "manage.py", "collectstatic", "--noinput", "--clear")
    }
    finally {
        if ($null -eq $previousSecret) { Remove-Item Env:\DJANGO_SECRET_KEY -ErrorAction SilentlyContinue }
        else { $env:DJANGO_SECRET_KEY = $previousSecret }
    }
    if (-not (Test-Path (Join-Path $repoRoot "public\index.html"))) {
        throw "BLOCKED: ไม่พบ public\index.html (หน้า splash) จึงไม่อัปโหลด Firebase Hosting"
    }
    if (-not (Test-Path (Join-Path $repoRoot "public\static\staticfiles.json"))) {
        throw "BLOCKED: collectstatic ไม่สร้าง public\static\staticfiles.json จึงไม่อัปโหลด Firebase Hosting"
    }

    Write-Host "กำลังอัปโหลดขึ้น Firebase Hosting (site: $FirebaseSite)..." -ForegroundColor Yellow
    Invoke-Checked -Executable "firebase" -Arguments @(
        "deploy", "--only", "hosting:$FirebaseSite",
        "--project", $ExpectedProject,
        "--non-interactive"
    )

    # --- ส่วนที่ 3: ตรวจว่าเว็บเปิดได้จริง (Cloud Run อาจกำลัง cold start จึงลองซ้ำได้ถึง ~60 วินาที) ---
    $smokeUrl = "$PublicUrl/home/"
    Write-Host "กำลังตรวจสอบว่าเว็บเปิดได้: $smokeUrl" -ForegroundColor Yellow
    $smokeOk = $false
    $deadline = (Get-Date).AddSeconds(60)
    do {
        try {
            $response = Invoke-WebRequest -Uri $smokeUrl -UseBasicParsing -TimeoutSec 30
            if ($response.StatusCode -eq 200) { $smokeOk = $true }
        }
        catch {
            Write-Host "  ยังไม่พร้อม รอลองใหม่..." -ForegroundColor DarkGray
        }
        if (-not $smokeOk) { Start-Sleep -Seconds 5 }
    } while (-not $smokeOk -and (Get-Date) -lt $deadline)

    if ($smokeOk) {
        Write-Host "OK: เว็บเปิดได้ปกติที่ $smokeUrl (deploy สำเร็จ)" -ForegroundColor Green
    }
    else {
        Write-Host "FAIL: deploy เสร็จแล้วแต่เปิด $smokeUrl ไม่ได้ภายใน 60 วินาที — โปรดตรวจเว็บด้วยตนเองและแจ้งผู้ดูแลระบบ" -ForegroundColor Red
        exit 1
    }
}
finally {
    Pop-Location
}
