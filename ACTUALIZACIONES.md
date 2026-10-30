# Actualizaciones automáticas desde GitHub

## Activarlas una sola vez

Los agentes anteriores no contienen un actualizador, por lo que necesitan esta última descarga manual. Enciende la VM, inicia sesión con el mismo usuario de Windows y conecta Tailscale.

1. Descarga el ZIP actualizado desde GitHub y extrae todos los archivos.
2. Cierra el agente anterior. Si estaba oculto, reinicia Windows; si ya tenía un inicio automático, detenlo antes de instalar esta migración.
3. Abre **Activar-actualizaciones.cmd** y pulsa **Instalar y activar actualizaciones**. No necesitas otra clave ni editar el JSON.
4. Opcionalmente marca «Iniciar el agente y el actualizador al entrar en Windows». Se crea o actualiza la tarea de inicio de sesión del mismo usuario, sin privilegios de administrador. No es un servicio anterior al inicio de sesión.
5. El agente y el actualizador continúan en segundo plano después de cerrar la ventana. En Corporaciones verás la versión y el estado del actualizador.

Iniciar-agente.cmd utiliza el actualizador instalado. Solicitar-ayuda.cmd y Permisos-equipo.cmd abren las herramientas de la versión activa. Para detener ambos procesos, usa **Detener-agente.cmd**: esperan al final del trabajo actual.

## Cómo se actualizan

La sede aprueba una versión con URL de GitHub fijada a un commit completo, tamaño y SHA-256. El agente recibe esa autorización por el gateway HTTPS autenticado; nunca envía su credencial de sucursal a GitHub. El permiso de actualizar se habilita localmente. Esto no es una firma digital de editor: la confianza depende de la sede, su certificado HTTPS y el control del repositorio y de las aprobaciones.

El actualizador busca versiones cada cinco minutos mientras está iniciado. Descargar no interrumpe el trabajo. Rechaza dominios distintos, URLs mutables, paquetes alterados, rutas fuera de la carpeta, enlaces y archivos de configuración. Descomprime en una carpeta de versión nueva, pide al agente que termine su trabajo actual y comprueba el arranque antes de cambiar la versión activa. No fuerza el cierre de tareas para actualizar.

Conserva la versión anterior. Si una candidata no completa el arranque o se cierra inesperadamente durante el primer minuto, intenta volver a la anterior y bloquea esa versión fallida. Esta prueba no detecta todos los errores funcionales: cada publicación debe pasar las pruebas centrales. No se repite automáticamente una tarea que ya se ejecutó.

No sobrescribe config.json, claves DPAPI, resultados pendientes, historial ni permisos de apagado e inferencia. La actualización puede tardar más si el agente espera confirmar un resultado con la sede. Si no hay Internet, GitHub o sede, conserva la versión instalada. Un equipo apagado no puede actualizarse; lo hará cuando vuelva a ejecutar el agente.

La versión inicial de esta migración es 1.1.0. La versión 1.1.1 se reserva para probar el ciclo de descarga, cambio y comunicación de versión; no añade permisos ni cambia las funciones de trabajo.

## Publicar una versión nueva desde la sede

1. Modificar y probar el código local, incrementando la versión de publicación.
2. Ejecutar scripts/build_agent_update.py --version X.Y.Z --notes "Descripción". Genera un ZIP y metadatos inmutables en artifacts/updates.
3. Subir el ZIP a updates/agent-X.Y.Z.zip en el repositorio autorizado. No incluir configuraciones, credenciales, resultados ni registros.
4. Obtener el SHA completo del commit y ejecutar scripts/approve_agent_release.ps1 -Version X.Y.Z -Commit SHA_COMPLETO. Comprobar que el ZIP publicado coincide con su SHA-256 local antes de aprobarlo.
5. La sede lo anunciará a los equipos que hayan optado por actualizar. Modificar un archivo de GitHub por sí solo no publica una actualización ejecutable.

El pequeño programa base de actualización tiene protocolo 1. Las versiones de agente compatibles se actualizan automáticamente; una futura migración de ese protocolo o de Python/Windows requiere un instalador nuevo explícito.

## Desactivar y revisar

Abre Activar-actualizaciones.cmd y pulsa Desactivar actualizaciones. Se aplica en la siguiente comprobación; no cancela una activación que ya haya comenzado. El agente y su posible tarea de inicio de sesión siguen funcionando. Los registros están en la carpeta local del agente: updater.log, managed-agent.log y update-status.json. No publiques la configuración, los archivos DPAPI ni resultados empresariales.
