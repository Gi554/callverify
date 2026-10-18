param([ValidateSet('portal','assurance')][string]$Service='portal')
$ErrorActionPreference='Stop'
Set-Location (Split-Path -Parent $PSScriptRoot)
$localEnv=Join-Path (Get-Location) '.env'
if(Test-Path -LiteralPath $localEnv){
    foreach($line in [IO.File]::ReadAllLines($localEnv)){
        if($line -match '^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=(.*)$'){
            [Environment]::SetEnvironmentVariable($matches[1],$matches[2].Trim(),'Process')
        }
    }
}
$env:DEBUG='true'
$serviceSettings=if($Service -eq 'portal'){'portal.backend.settings'}else{'apps.assurance.backend.settings'}
$servicePort=if($Service -eq 'portal'){8090}else{8091}
& .venv/Scripts/python.exe manage.py migrate --settings=$serviceSettings
if($LASTEXITCODE -ne 0){exit $LASTEXITCODE}
& .venv/Scripts/python.exe manage.py runserver "127.0.0.1:$servicePort" --settings=$serviceSettings
