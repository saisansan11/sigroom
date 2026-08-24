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
if (-not $backupSetting) { throw "กรุณากำหนด BACKUP_DIR ใน .env" }
$backupDir = if ([IO.Path]::IsPathRooted($backupSetting)) { $backupSetting } else { Join-Path $projectDir $backupSetting }
$backupDir = [IO.Path]::GetFullPath($backupDir)
$latest = Get-ChildItem -LiteralPath $backupDir -Filter "sigroom-*.dump" -File | Sort-Object LastWriteTime -Descending | Select-Object -First 1
if (-not $latest) { throw "ไม่พบไฟล์สำรองใน $backupDir ให้รัน scripts\backup.ps1 ก่อน" }

$restoreDb = "ogn_room_restore_test"
$dropDb = Find-PgTool "dropdb"
$createDb = Find-PgTool "createdb"
$pgRestore = Find-PgTool "pg_restore"
$psql = Find-PgTool "psql"
$previousPassword = $env:PGPASSWORD

try {
    $env:PGPASSWORD = $config["DB_PASSWORD"]
    & $dropDb --if-exists --host=$($config["DB_HOST"]) --port=$($config["DB_PORT"]) --username=$($config["DB_USER"]) $restoreDb
    if ($LASTEXITCODE -ne 0) { throw "ลบฐานทดสอบเดิมไม่สำเร็จ" }
    & $createDb --host=$($config["DB_HOST"]) --port=$($config["DB_PORT"]) --username=$($config["DB_USER"]) $restoreDb
    if ($LASTEXITCODE -ne 0) { throw "สร้างฐานทดสอบไม่สำเร็จ" }
    & $pgRestore --no-owner --no-privileges --host=$($config["DB_HOST"]) --port=$($config["DB_PORT"]) --username=$($config["DB_USER"]) --dbname=$restoreDb $latest.FullName
    if ($LASTEXITCODE -ne 0) { throw "กู้ไฟล์สำรองไม่สำเร็จ" }
    $sourceCount = (& $psql -X -t -A --host=$($config["DB_HOST"]) --port=$($config["DB_PORT"]) --username=$($config["DB_USER"]) --dbname=$($config["DB_NAME"]) --command="SELECT COUNT(*) FROM bookings_booking;").Trim()
    $restoredCount = (& $psql -X -t -A --host=$($config["DB_HOST"]) --port=$($config["DB_PORT"]) --username=$($config["DB_USER"]) --dbname=$restoreDb --command="SELECT COUNT(*) FROM bookings_booking;").Trim()
    if ($LASTEXITCODE -ne 0) { throw "นับข้อมูลหลัง restore ไม่สำเร็จ" }
    if ($sourceCount -ne $restoredCount) { throw "จำนวน Booking ไม่ตรง: ฐานจริง $sourceCount / ฐานกู้คืน $restoredCount" }
    Write-Host "ผ่าน — กู้ $($latest.Name) สำเร็จ และ Booking ตรงกัน $sourceCount แถว"
}
catch {
    Write-Error "ไม่ผ่าน — $($_.Exception.Message)"
    exit 1
}
finally {
    $env:PGPASSWORD = $previousPassword
}
