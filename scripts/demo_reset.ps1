# Deja la base de datos en el estado inicial de la demo (la vacia y la vuelve a sembrar). Windows sin Docker.
#
#   .\scripts\demo_reset.ps1
#
# Usa el DATABASE_URL del entorno o del .env de la raiz (sin .env: SQLite en services/api/hackemate.db).
# OJO: borra TODO lo creado durante el ensayo. No hace falta reiniciar la api.
# Con Docker usar scripts/demo_reset.sh (sin --local).
$ErrorActionPreference = 'Stop'

$raiz = Split-Path -Parent $PSScriptRoot
Push-Location $raiz
try {
    $reloj = [System.Diagnostics.Stopwatch]::StartNew()
    Write-Host '==> Reiniciando la demo en local (python scripts/seed.py --reset)...'
    & python scripts/seed.py --reset
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: el seed ha fallado (codigo $LASTEXITCODE)" -ForegroundColor Red
        exit $LASTEXITCODE
    }
    $reloj.Stop()
    Write-Host ('==> Demo reiniciada en {0:N1} s' -f $reloj.Elapsed.TotalSeconds) -ForegroundColor Green
}
finally {
    Pop-Location
}
