$ErrorActionPreference = "Stop"
$projectDir = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectDir
uv run waitress-serve --listen=0.0.0.0:8000 config.wsgi:application
