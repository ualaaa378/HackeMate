# Smoke test de la API (solo HTTP). Comprueba las rutas que sostienen el guion de la demo. Windows PowerShell 5.1+.
#
#   .\scripts\smoke_test.ps1
#   $env:API_URL='http://localhost:8000'; $env:BOT_URL='http://localhost:8001'; .\scripts\smoke_test.ps1
#
# Variables: API_URL (por defecto http://localhost:8000), INTERNAL_TOKEN (si no esta en el entorno se lee
# del .env de la raiz; por defecto "cambia-esto") y BOT_URL (opcional: si esta, tambien se mira su /health).
# Necesita los datos de la demo cargados (scripts\demo_reset.ps1). Sale con codigo 1 si algo falla.
$ErrorActionPreference = 'Stop'
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch { }

$raiz = Split-Path -Parent $PSScriptRoot
$apiUrl = if ($env:API_URL) { $env:API_URL.TrimEnd('/') } else { 'http://localhost:8000' }
$token = $env:INTERNAL_TOKEN
if (-not $token -and (Test-Path (Join-Path $raiz '.env'))) {
    $linea = Get-Content (Join-Path $raiz '.env') | Where-Object { $_ -match '^INTERNAL_TOKEN=' } | Select-Object -Last 1
    if ($linea) { $token = ($linea -replace '^INTERNAL_TOKEN=', '').Trim().Trim('"') }
}
if (-not $token) { $token = 'cambia-esto' }
$botUrl = $env:BOT_URL

$rutaSolidaria = '1e5d0000-0000-4000-8000-000000000001'
$carmen = '5a5e0000-0000-4000-8000-000000000001'
$interno = @{ 'X-Internal-Token' = $token }
$script:fallos = 0

function Ok($texto) { Write-Host "  [OK]    $texto" -ForegroundColor Green }
function Fallo($texto) { Write-Host "  [FALLO] $texto" -ForegroundColor Red; $script:fallos++ }

# Devuelve @{ Codigo; Tipo; Texto; Json } sin lanzar excepcion en 4xx/5xx ni si el servicio no responde
function Pedir($url, $cabeceras = @{}) {
    try {
        $r = Invoke-WebRequest -Uri $url -Headers $cabeceras -UseBasicParsing -TimeoutSec 15
        # El cuerpo se decodifica como UTF-8 aunque la respuesta no declare charset
        $texto = [System.Text.Encoding]::UTF8.GetString($r.RawContentStream.ToArray())
        $res = @{ Codigo = [int]$r.StatusCode; Tipo = [string]$r.Headers['Content-Type']; Texto = $texto; Json = $null }
    }
    catch {
        $codigo = 0
        $texto = $_.Exception.Message
        if ($_.Exception.Response) {
            $codigo = [int]$_.Exception.Response.StatusCode
            # En PowerShell 5.1 el cuerpo del error llega en ErrorDetails
            if ($_.ErrorDetails -and $_.ErrorDetails.Message) { $texto = $_.ErrorDetails.Message }
        }
        $res = @{ Codigo = $codigo; Tipo = ''; Texto = $texto; Json = $null }
    }
    if ($res.Tipo -like 'application/json*') {
        try { $res.Json = $res.Texto | ConvertFrom-Json } catch { }
    }
    return $res
}

function Corto($texto) { if ($texto.Length -gt 200) { $texto.Substring(0, 200) } else { $texto } }

Write-Host "Smoke test contra $apiUrl"

# 1. /health
$r = Pedir "$apiUrl/health"
if ($r.Codigo -eq 200 -and $r.Json.status -eq 'ok') { Ok "GET /health -> ok (version $($r.Json.version))" }
else { Fallo "GET /health -> HTTP $($r.Codigo) $(Corto $r.Texto)" }

# 2. Agenda
$r = Pedir "$apiUrl/api/v1/eventos"
$total = if ($r.Json) { [int]$r.Json.total } else { 0 }
if ($r.Codigo -eq 200 -and $total -gt 0) { Ok "GET /api/v1/eventos -> $total eventos" }
else { Fallo "GET /api/v1/eventos -> HTTP $($r.Codigo), total=$total (falta sembrar? scripts\demo_reset.ps1)" }

# 3. Ficha de la Ruta Solidaria
$r = Pedir "$apiUrl/api/v1/eventos/$rutaSolidaria"
if ($r.Codigo -eq 200 -and $r.Json.id -eq $rutaSolidaria) { Ok "GET /api/v1/eventos/{ruta} -> $($r.Json.titulo) [$($r.Json.estado)]" }
else { Fallo "GET /api/v1/eventos/$rutaSolidaria -> HTTP $($r.Codigo) $(Corto $r.Texto)" }

# 4. Municipios
$r = Pedir "$apiUrl/api/v1/municipios"
$n = 0
if ($r.Json) { $n = if ($r.Json.items) { @($r.Json.items).Count } else { @($r.Json).Count } }
if ($r.Codigo -eq 200 -and $n -ge 5) { Ok "GET /api/v1/municipios -> $n pueblos" }
else { Fallo "GET /api/v1/municipios -> HTTP $($r.Codigo), pueblos=$n (se esperaban 5)" }

# 5. Bandeja de moderacion con token interno
$r = Pedir "$apiUrl/api/v1/moderacion/pendientes" $interno
if ($r.Codigo -eq 200) { Ok "GET /api/v1/moderacion/pendientes (X-Internal-Token) -> $($r.Json.total) pendientes" }
else { Fallo "GET /api/v1/moderacion/pendientes -> HTTP $($r.Codigo) (INTERNAL_TOKEN distinto del de la api?) $(Corto $r.Texto)" }

# 6. Recomendaciones de Carmen: la Ruta Solidaria primera
$r = Pedir "$apiUrl/api/v1/recomendaciones?usuario_id=$carmen" $interno
$primera = $null
if ($r.Json -and $r.Json.items) { $primera = @($r.Json.items)[0] }
if ($r.Codigo -eq 200 -and $primera -and $primera.evento.id -eq $rutaSolidaria) { Ok "GET /api/v1/recomendaciones (Carmen) -> Ruta Solidaria primera: $($primera.motivo)" }
else { Fallo "GET /api/v1/recomendaciones (Carmen) -> HTTP $($r.Codigo), primera='$($primera.evento.id)' (se esperaba la Ruta Solidaria)" }

# 7. Calendario .ics
$r = Pedir "$apiUrl/api/v1/eventos/$rutaSolidaria/ics"
if ($r.Codigo -eq 200 -and $r.Tipo -like 'text/calendar*' -and $r.Texto -match 'BEGIN:VCALENDAR') { Ok "GET /api/v1/eventos/{ruta}/ics -> $($r.Tipo)" }
else { Fallo "GET /api/v1/eventos/$rutaSolidaria/ics -> HTTP $($r.Codigo), Content-Type '$($r.Tipo)'" }

# 8. (Opcional) /health del bot
if ($botUrl) {
    $botUrl = $botUrl.TrimEnd('/')
    $r = Pedir "$botUrl/health"
    if ($r.Codigo -eq 200 -and $r.Json.status -eq 'ok') { Ok "GET $botUrl/health -> ok" }
    else { Fallo "GET $botUrl/health -> HTTP $($r.Codigo) $(Corto $r.Texto)" }
}
else { Write-Host '  [--]    BOT_URL sin definir: no se comprueba el bot' }

Write-Host ''
if ($script:fallos -eq 0) {
    Write-Host 'SMOKE TEST EN VERDE' -ForegroundColor Green
    exit 0
}
Write-Host "SMOKE TEST EN ROJO: $($script:fallos) comprobaciones fallidas" -ForegroundColor Red
exit 1
