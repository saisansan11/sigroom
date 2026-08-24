$ErrorActionPreference = "Stop"

function Read-DotEnv([string]$Path) {
    $values = @{}
    foreach ($line in Get-Content -LiteralPath $Path -Encoding UTF8) {
        $trimmed = $line.Trim()
        if (-not $trimmed -or $trimmed.StartsWith("#") -or -not $trimmed.Contains("=")) { continue }
        $name, $value = $trimmed.Split("=", 2)
        $values[$name.Trim()] = $value.Trim().Trim('"').Trim("'")
    }
    return $values
}

function Find-PgTool([string]$Name) {
    $command = Get-Command "$Name.exe" -ErrorAction SilentlyContinue
    if ($command) { return $command.Source }
    $fallback = Join-Path "C:\Program Files\PostgreSQL\16\bin" "$Name.exe"
    if (Test-Path -LiteralPath $fallback) { return $fallback }
    throw "ไม่พบ $Name.exe กรุณาติดตั้ง PostgreSQL 16 หรือเพิ่มโฟลเดอร์ bin ใน PATH"
}

$projectDir = Split-Path -Parent $PSScriptRoot
$envFile = Join-Path $projectDir ".env"
if (-not (Test-Path -LiteralPath $envFile)) { throw "ไม่พบ $envFile" }
$config = Read-DotEnv $envFile
$backupSetting = if ($env:SIGROOM_BACKUP_DIR) { $env:SIGROOM_BACKUP_DIR } else { $config["BACKUP_DIR"] }
if (-not $backupSetting) { throw "กรุณากำหนด BACKUP_DIR ใน .env ให้เป็นดิสก์หรือแชร์คนละเครื่อง" }
$backupDir = if ([IO.Path]::IsPathRooted($backupSetting)) { $backupSetting } else { Join-Path $projectDir $backupSetting }
$backupDir = [IO.Path]::GetFullPath($backupDir)
New-Item -ItemType Directory -Force -Path $backupDir | Out-Null
$logPath = Join-Path $backupDir "backup-log.txt"
$dumpPath = Join-Path $backupDir ("sigroom-{0}.dump" -f (Get-Date -Format "yyyyMMdd-HHmm"))
$pgDump = Find-PgTool "pg_dump"
$previousPassword = $env:PGPASSWORD

try {
    $env:PGPASSWORD = $config["DB_PASSWORD"]
    & $pgDump -Fc --host=$($config["DB_HOST"]) --port=$($config["DB_PORT"]) --username=$($config["DB_USER"]) --file=$dumpPath $config["DB_NAME"]
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $dumpPath)) { throw "pg_dump ทำงานไม่สำเร็จ (exit $LASTEXITCODE)" }
    $oldBackups = Get-ChildItem -LiteralPath $backupDir -Filter "sigroom-*.dump" -File | Sort-Object LastWriteTime -Descending | Select-Object -Skip 30
    foreach ($oldBackup in $oldBackups) { Remove-Item -LiteralPath $oldBackup.FullName -Force }
    Add-Content -LiteralPath $logPath -Encoding UTF8 -Value "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') SUCCESS $dumpPath"
    Write-Host "สำรองสำเร็จ: $dumpPath"
    Write-Host "คงเหลือ $((Get-ChildItem -LiteralPath $backupDir -Filter 'sigroom-*.dump' -File).Count) ชุด (สูงสุด 30)"
}
catch {
    Add-Content -LiteralPath $logPath -Encoding UTF8 -Value "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') FAILED $($_.Exception.Message)"
    Write-Error $_
    exit 1
}
finally {
    $env:PGPASSWORD = $previousPassword
}
