# AI Corporation — agente de sucursal Windows, protocolo v1

Agente pequeño que consulta la sede por HTTPS. No contiene modelos ni datos de empresas. Los perfiles de coordinador, operaciones, soporte y calidad se definen en la sede y se usan al asignar trabajos. No ejecuta comandos del sistema ni lee carpetas de negocio.

## Requisitos de la VM

- Windows 11 o Windows Server y Python 3.12 o posterior instalado desde https://www.python.org/downloads/windows/ .
- Acceso HTTPS válido al gateway de la sede (normalmente `https://<equipo>.<red>.ts.net:8443`). Si usas Tailscale, instala su cliente y autoriza el dispositivo conforme a la política de red de la sede.
- Para la primera prueba no necesitas Ollama ni GPU. La inferencia queda desactivada de forma predeterminada.

## Instalar desde el repositorio

Clona este repositorio con Git o descarga el ZIP desde GitHub y extráelo. Revisa `agent.py` e `install.ps1`. Desde PowerShell, situado en la carpeta del agente:

```powershell
.\install.ps1 -CentralUrl 'https://NOMBRE-DE-LA-SEDE.ts.net:8443' -Label 'VM Windows de pruebas'
```

El instalador solicita la clave de alta con entrada oculta. Créala justo antes en **Corporaciones → empresa → Crear clave de instalación**. Caduca en 15 minutos y solo vale una vez. No uses el token de Telegram. Las credenciales se cifran con DPAPI para el usuario de Windows y se guardan en `%LOCALAPPDATA%\AI Corporation Agent\config.json`.

Ejecuta la prueba que muestra el instalador:

```powershell
python "$env:LOCALAPPDATA\AI Corporation Agent\agent.py" --config "$env:LOCALAPPDATA\AI Corporation Agent\config.json" --once
```

Desde la sede verás el equipo conectado. Activa la corporación y envíale una prueba **echo**; vuelve a ejecutar el agente con `--once` y comprueba el resultado. Repite con inventario: solo devuelve sistema operativo, versión de Python, porcentaje de RAM y si Ollama se ha habilitado/detectado. No devuelve usuarios, direcciones IP, nombres de equipo, archivos o procesos.

Para dejarlo consultando cada 30 segundos, ejecuta el mismo comando sin `--once`. La empresa inactiva permite el contacto básico pero no entrega trabajos.

## Inicio opcional y modelos

En una instalación nueva, `-StartWorker` lo inicia en segundo plano con registros locales; `-InstallStartupTask` crea una tarea de Windows al iniciar sesión, bajo ese mismo usuario y sin elevar privilegios. No funciona como servicio de sistema antes de iniciar sesión. El instalador no sobrescribe configuraciones existentes.

Para usar IA, instala Ollama y el modelo en la VM, revisa la carga que soporta y habilita `allow_compute` en su configuración (o usa `-AllowCompute` durante la instalación inicial). La lista `allowed_models` limita los modelos permitidos; su valor inicial es `qwen3:8b`. No hay descarga automática de modelos. Una VM sin GPU puede ser demasiado lenta para ese modelo; elige un modelo que quepa en la VM y actualiza tanto el perfil central como la lista local permitida.

## Límites de esta versión

- Solo trabajos `echo`, `inventory` y `generate` (texto con Ollama local). Ningún shell, escritura de documentos de empresa, RDP ni herramientas de terceros.
- Un trabajo simultáneo por equipo; un resultado tiene plazo de 10 minutos. Si caduca, requiere revisión y no se repite automáticamente.
- Si se pierde la red después de ejecutar, se conserva un resultado cifrado local para reenviarlo. Si ya caducó, se guarda como `undelivered-*.dpapi` para revisión.
- Revocar el equipo impide recoger trabajos y enviar resultados. Una inferencia ya iniciada puede terminar localmente; no es un mecanismo de apagado remoto inmediato.
- Es un piloto para una VM. No se ha instalado ni auditado en servidores reales de una empresa. No conecta datos de negocio automáticamente.

## Separación de red

El gateway de equipos es distinto del panel: puerto local 8001, normalmente HTTPS externo 8443. El panel administrativo usa 443/8000 y no debe concederse a los equipos de empresas ajenas. La política de Tailscale o el cortafuegos debe permitir a las sucursales **solo** el gateway. Compartir una cuenta/red con acceso amplio también daría acceso a otros servicios de esa red: una credencial de agente no sustituye esas reglas de red. El piloto en tu propia VM no configura automáticamente políticas de otras empresas.

El servidor no solicita ni guarda contraseñas de servidores remotos. Nunca publiques claves de alta, credenciales, `config.json`, registros o resultados en GitHub.
