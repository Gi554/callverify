param([switch]$Test)
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path -Parent $PSScriptRoot)
# Load the private local configuration without displaying its values.
$localEnvPath = Join-Path (Get-Location) '.env'
if (Test-Path -LiteralPath $localEnvPath) {
    foreach ($line in [IO.File]::ReadAllLines($localEnvPath)) {
        if ($line -match '^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=(.*)$') {
            [Environment]::SetEnvironmentVariable($matches[1], $matches[2].Trim(), 'Process')
        }
    }
}
$env:DEBUG = 'true'
$env:CELERY_EAGER = 'true'
if ($Test) {
    & .venv/Scripts/python.exe manage.py test
} else {
    & .venv/Scripts/python.exe manage.py migrate
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    & .venv/Scripts/python.exe manage.py runserver 127.0.0.1:8000
}
