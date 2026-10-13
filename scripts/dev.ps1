param([switch]$Test)
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path -Parent $PSScriptRoot)
$env:DEBUG = 'true'
$env:CELERY_EAGER = 'true'
if ($Test) {
    & .venv/Scripts/python.exe manage.py test
} else {
    & .venv/Scripts/python.exe manage.py migrate
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    & .venv/Scripts/python.exe manage.py runserver 127.0.0.1:8000
}
