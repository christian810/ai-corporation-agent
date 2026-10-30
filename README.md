## Actualización: sucursales ligeras e IA central

Consulta [SEDE_CENTRAL.md](SEDE_CENTRAL.md) para actualizar el agente conservando sus credenciales.

- **Iniciar-agente.cmd**: agente con latido independiente cada 5 segundos; desconexión tras 20 segundos sin comunicación, más el refresco de pantalla.
- **Solicitar-ayuda.cmd**: ventana para pedir ayuda a los especialistas de la sede, sin instalar Ollama ni modelos en la sucursal. Incluye una prueba de ida y vuelta sin IA.
- La sede procesa texto por áreas: soporte, red, contabilidad y proyectos. Las solicitudes y resultados aparecen en Corporaciones. Todavía no ejecuta cambios de red ni operaciones contables.

Validado con pruebas automatizadas y procesos Windows separados, incluida una respuesta real del modelo central. La prueba en tu VM se realiza después de actualizarla.

---

## Instalación sencilla con ventana (recomendada)

1. En la VM, conecta Tailscale e instala Python 3.12 o posterior con Tcl/Tk y la opción Add Python to PATH.
2. Descarga este repositorio con **Code → Download ZIP** y extrae todos los archivos.
3. Haz doble clic en **Conectar-sucursal.cmd**. Debe estar junto a `setup_gui.py` y `agent.py`.
4. Comprueba la dirección HTTPS del gateway (puerto 8443), escribe el nombre del equipo y pega una **clave de alta nueva** generada en Corporaciones.
5. Pulsa **Conectar e iniciar agente**. La clave se cifra automáticamente; no edites el JSON.

El asistente puede reemplazar la configuración de un alta todavía incompleta. Si ya hay un equipo dado de alta, conserva sus credenciales y no inicia otro proceso. Comprueba HTTPS y muestra errores de conexión o clave caducada sin revelar credenciales. El agente arranca en segundo plano, con inferencia desactivada. Este método no configura inicio automático después de reiniciar Windows.

La prueba real en tu VM sigue pendiente. Si aparece un error, comparte únicamente su mensaje.

---

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


## Solucionar el primer arranque en Windows

Si el instalador ha indicado «Instalado», no lo repitas todavía. Ejecuta estos pasos en PowerShell dentro de la máquina virtual y con el mismo usuario de Windows que instaló el agente.

1. Si aparece el indicador `>>`, pulsa **Ctrl+C** para cancelar el comando incompleto.
2. Copia estas líneas **una por una**, conservando las comillas y las barras invertidas:

```powershell
$carpeta = Join-Path $env:LOCALAPPDATA 'AI Corporation Agent'
Test-Path "$carpeta\config.json"
```

La segunda línea debe devolver `True`. Si devuelve `False`, detente y comprueba el usuario de Windows y la instalación; no borres ninguna configuración.

3. Ejecuta la prueba de conexión y alta:

```powershell
python "$carpeta\agent.py" --config "$carpeta\config.json" --once
```

La ruta correcta termina en `Agent\config.json`, con una barra entre la carpeta y el archivo; `Agentconfig.json` no es válida. No copies el prefijo `PS C:\...>` de la consola.

Si aparece «Equipo vinculado a la corporación», el alta se ha completado. Una corporación `INACTIVE` puede conectarse, pero no recibe trabajos hasta que su propietario la active en la sede. Con `--once`, el proceso termina después de una consulta: es normal.

Si falla, comprueba que Tailscale esté conectado **también en la VM** y abre la dirección del gateway seguida de `/health` (puerto HTTPS 8443). Debe responder con `corporation-agent-gateway`. Comparte solo el mensaje de error: nunca claves, tokens ni el contenido de `config.json`.


## Comprobar el JSON y la clave cifrada

El campo `credential_protected` contiene una credencial cifrada por el instalador con DPAPI de Windows. **No pegues una clave sin cifrar en ese campo ni copies el JSON desde otro equipo o usuario.** Debe leerse con el mismo usuario y equipo Windows donde se instaló.

Ejecuta este bloque en PowerShell de la VM. Solo muestra comprobaciones; no imprime la credencial:

```powershell
$carpeta = Join-Path $env:LOCALAPPDATA 'AI Corporation Agent'
try {
    $c = Get-Content "$carpeta\config.json" -Raw -ErrorAction Stop | ConvertFrom-Json -ErrorAction Stop
    "JSON correcto: Sí"
    "Alta completada: $($c.enrolled)"
    "Tiene credencial: $(-not [string]::IsNullOrWhiteSpace($c.credential_protected))"
    "Parece cifrada por Windows: $([string]$c.credential_protected -match '^01000000d08c9ddf')"
} catch {
    "No se encuentra el archivo o el JSON no es válido."
}
```

Interpretación:

- `JSON correcto: Sí`: el archivo se ha podido leer y analizar. No confirma que todos sus campos sean correctos.
- `Alta completada: False`: el agente todavía necesita completar el alta con la sede. No demuestra por sí solo un error.
- `Tiene credencial: False`: falta la credencial o está vacía.
- `Parece cifrada por Windows: False`: el contenido no tiene el encabezado esperado; puede haberse editado o pegado la clave sin cifrar.
- `Parece cifrada por Windows: True`: solo comprueba el formato inicial. No prueba que se pueda descifrar, que sea válida o que siga vigente.

La clave inicial de alta caduca en **15 minutos** y solo se puede usar una vez. Después del alta se sustituye por la credencial del equipo; esta no tiene ese plazo de 15 minutos. No borres ni sustituyas el JSON antes de revisar el estado. Comparte únicamente las respuestas de esta comprobación, nunca el archivo, claves o tokens.
