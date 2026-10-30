param([string]$CentralUrl='https://chris.tail91e028.ts.net:8443')
$ErrorActionPreference='Stop'
Write-Host 'Diagnostico de sucursal (no muestra credenciales)'
$python=Get-Command python -ErrorAction SilentlyContinue
if ($python) {
    & $python.Source -c "import sys; print('Python: '+sys.version.split()[0]); sys.exit(0 if sys.version_info >= (3,12) else 1)"
    if ($LASTEXITCODE -ne 0) { Write-Host 'FALLO: se requiere Python 3.12 o posterior.' }
} else { Write-Host 'FALLO: Python no esta disponible en esta terminal.' }
try {
    $health=Invoke-RestMethod ($CentralUrl.TrimEnd('/')+'/health') -TimeoutSec 15
    if ($health.service -ne 'corporation-agent-gateway' -or $health.protocol -ne 1) { throw 'La direccion no corresponde al gateway de agentes.' }
    Write-Host 'HTTPS y gateway: OK'
} catch {
    Write-Host 'FALLO de conexion: comprueba Tailscale conectado en esta VM, la sede encendida y el puerto 8443.'
    Write-Host $_.Exception.Message
}
$configPath=Join-Path $env:LOCALAPPDATA 'AI Corporation Agent\config.json'
if (Test-Path -LiteralPath $configPath) {
    try {
        $config=Get-Content -LiteralPath $configPath -Raw | ConvertFrom-Json
        Write-Host ('Configuracion existente. Alta completada: '+[bool]$config.enrolled)
        Write-Host ('Direccion coincide: '+($config.central_url.TrimEnd('/') -eq $CentralUrl.TrimEnd('/')))
        Write-Host ('Inferencia habilitada: '+[bool]$config.allow_compute)
    } catch { Write-Host 'FALLO: configuracion local ilegible. No la borres; revisaremos su recuperacion.' }
} else { Write-Host 'Todavia no hay configuracion instalada para este usuario de Windows.' }
Write-Host 'Puedes compartir esta salida; no compartas config.json ni claves de alta.'
