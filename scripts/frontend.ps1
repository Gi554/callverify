$ErrorActionPreference = 'Stop'
Set-Location (Join-Path (Split-Path -Parent $PSScriptRoot) 'frontend')
$nodeCommand = Get-Command node -ErrorAction SilentlyContinue
if ($nodeCommand) {
    & $nodeCommand.Source node_modules/vite/bin/vite.js --host 127.0.0.1
} else {
    $bundledNode = Join-Path $env:USERPROFILE '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe'
    if (-not (Test-Path -LiteralPath $bundledNode)) { throw 'Installez Node.js pour lancer le frontend.' }
    & $bundledNode node_modules/vite/bin/vite.js --host 127.0.0.1
}
