param(
    [Parameter(Mandatory=$true)][string]$CentralUrl,
    [string]$Label = 'Sucursal Windows',
    [switch]$AllowCompute,
    [switch]$InstallStartupTask,
    [switch]$StartWorker
)
$ErrorActionPreference='Stop'
if ($env:OS -ne 'Windows_NT') { throw 'Este instalador es para Windows.' }
$pythonCommand=Get-Command python -ErrorAction SilentlyContinue
if (!$pythonCommand) { throw 'Instala Python 3.12 o posterior desde python.org antes de continuar.' }
& $pythonCommand.Source -c "import sys; assert sys.version_info >= (3,12)"
if ($LASTEXITCODE -ne 0) { throw 'Se requiere Python 3.12 o posterior.' }
$parsedUrl=[Uri]$CentralUrl
if ($parsedUrl.Scheme -ne 'https' -or $parsedUrl.UserInfo -or $parsedUrl.Query -or $parsedUrl.Fragment -or $parsedUrl.AbsolutePath -ne '/') { throw 'Usa la dirección HTTPS base del gateway, sin rutas ni credenciales.' }
try {
    $health=Invoke-RestMethod ($CentralUrl.TrimEnd('/')+'/health') -TimeoutSec 15
    if ($health.service -ne 'corporation-agent-gateway' -or $health.protocol -ne 1) { throw 'La direccion no es el gateway de agentes.' }
} catch { throw 'No se puede verificar el gateway HTTPS. Comprueba Tailscale en esta VM y ejecuta diagnose.ps1 antes de introducir una clave.' }
$installRoot=Join-Path $env:LOCALAPPDATA 'AI Corporation Agent'
New-Item -ItemType Directory -Force -Path $installRoot | Out-Null
$configPath=Join-Path $installRoot 'config.json'
if (Test-Path -LiteralPath $configPath) { throw 'Ya existe una instalación. Conserva su configuración; no se sobrescribe la credencial.' }
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'agent.py') -Destination (Join-Path $installRoot 'agent.py')
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'update_common.py') -Destination (Join-Path $installRoot 'update_common.py')
$bootstrap=Read-Host 'Clave de alta de un solo uso (no el token de Telegram)' -AsSecureString
$config=@{central_url=$CentralUrl.TrimEnd('/');label=$Label;credential_protected='';enrolled=$false;allow_compute=[bool]$AllowCompute;allowed_models=@('qwen3:8b');poll_seconds=30}
# ConvertFrom-SecureString uses Windows DPAPI but its envelope differs from raw CryptProtectData.
# Convert the secure input directly to a raw DPAPI blob using the same Windows API as the agent.
$bstr=[Runtime.InteropServices.Marshal]::SecureStringToBSTR($bootstrap)
try {
    Add-Type -AssemblyName System.Security
    $bytes=[Text.Encoding]::UTF8.GetBytes([Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr))
    $blob=[Security.Cryptography.ProtectedData]::Protect($bytes,$null,[Security.Cryptography.DataProtectionScope]::CurrentUser)
    $config.credential_protected=([BitConverter]::ToString($blob)).Replace('-','').ToLowerInvariant()
    [Array]::Clear($bytes,0,$bytes.Length)
} finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr) }
$config | ConvertTo-Json | Set-Content -LiteralPath $configPath -Encoding UTF8
# PS 5.1 writes UTF-8 BOM; Python reads this with utf-8-sig.
if ($InstallStartupTask) {
    $arguments='"'+(Join-Path $installRoot 'agent.py')+'" --config "'+$configPath+'"'
    $action=New-ScheduledTaskAction -Execute $pythonCommand.Source -Argument $arguments
    $trigger=New-ScheduledTaskTrigger -AtLogOn -User ([Security.Principal.WindowsIdentity]::GetCurrent().Name)
    $principal=New-ScheduledTaskPrincipal -UserId ([Security.Principal.WindowsIdentity]::GetCurrent().Name) -LogonType Interactive -RunLevel Limited
    Register-ScheduledTask -TaskName 'AI Corporation Branch Agent' -Action $action -Trigger $trigger -Principal $principal -Description 'Agente de sucursal; solo trabajos de texto autorizados.' | Out-Null
}
Write-Host "Instalado en $installRoot. Inferencia local: $([bool]$AllowCompute)."
if ($StartWorker) {
    Start-Process -FilePath $pythonCommand.Source -ArgumentList @(('"'+(Join-Path $installRoot 'agent.py')+'"'),'--config',('"'+$configPath+'"')) -WindowStyle Hidden -RedirectStandardOutput (Join-Path $installRoot 'agent.log') -RedirectStandardError (Join-Path $installRoot 'agent-error.log')
} else {
    Write-Host 'Prueba manual (sin programar un inicio automático):'
    Write-Host ('python "'+(Join-Path $installRoot 'agent.py')+'" --config "'+$configPath+'" --once')
}
