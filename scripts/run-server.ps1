$ErrorActionPreference = "Stop"
$projectDir = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectDir

# หา uv.exe ให้ได้แม้รันจาก Task Scheduler ที่ PATH ไม่ครบ
$uvCommand = Get-Command "uv.exe" -ErrorAction SilentlyContinue
$uvPath = if ($uvCommand) { $uvCommand.Source } else { Join-Path $env:USERPROFILE ".local\bin\uv.exe" }
if (-not (Test-Path -LiteralPath $uvPath)) { throw "ไม่พบ uv.exe — ติดตั้ง uv หรือแก้ path ในสคริปต์นี้" }

& $uvPath run waitress-serve --listen=0.0.0.0:8000 config.wsgi:application
# ส่ง exit code ของ Waitress กลับให้ Task Scheduler เห็นว่า server ล้ม เพื่อให้เงื่อนไข restart on failure ทำงาน
exit $LASTEXITCODE
