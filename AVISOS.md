# Mostrar un aviso en la VM

Esta actualización añade el trabajo `desktop_notice`: un mensaje Windows de texto plano, sin shell ni IA. Se cierra al pulsar Aceptar o tras 20 segundos. Solo aparece en la sesión donde ejecutas el agente; no garantiza mostrarse sobre la pantalla de bloqueo o en otra sesión RDP.

Para actualizar un equipo ya conectado:

1. Descarga el ZIP actualizado de GitHub y extrae todos los archivos en la VM.
2. Reinicia la VM para detener el agente anterior. Inicia sesión con el mismo usuario y conecta Tailscale. Este paso asume que no configuraste el inicio automático opcional del agente anterior; si lo configuraste, detén ese proceso antes de iniciar otro.
3. Abre `Iniciar-agente.cmd` en la carpeta recién extraída. Usa las credenciales existentes: no introduzcas otra clave ni edites el JSON. Mantén esa ventana abierta; cerrarla detiene este agente.
4. Desde la sede, en Corporaciones, selecciona la empresa, el equipo y «Mostrar aviso en pantalla». Escribe el mensaje y envíalo.

El resultado distingue cierre del usuario y cierre automático. Un resultado correcto acredita que Windows mostró el aviso, no que una persona haya leído su contenido. Los agentes anteriores rechazan este tipo de trabajo, por lo que debes actualizarlos antes de enviarlo.
