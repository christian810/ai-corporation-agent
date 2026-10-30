# Apagar el equipo de sucursal desde Telegram

1. Descarga y extrae el ZIP actualizado. Cierra el agente anterior de la VM.
2. Abre **Permisos-equipo.cmd**, marca «Permitir apagado remoto confirmado desde Telegram» y guarda. Este permiso solo se habilita localmente; no hay elevación de privilegios.
3. Abre **Iniciar-agente.cmd** de la carpeta nueva. Mantén la ventana abierta.
4. Desde tu chat privado con el bot vinculado, envía `/equipos`. Comprueba que **VM EmpresaX** anuncia apagado permitido.
5. Guarda los documentos de la VM y envía `/apagar EmpresaX`, o `/tarea apagar el equipo de EmpresaX`.
6. El bot mostrará empresa, equipo e ID. Pulsa **Confirmar apagado** solo si ese es el destino correcto. La confirmación caduca en dos minutos. Usa el ID de `/equipos` si una empresa tiene varios equipos.

El agente pide apagar su propio Windows sin `/f` ni cierre forzado. Las aplicaciones pueden bloquearlo y el usuario debe tener permiso de Windows para apagar. La central no puede encenderlo después: reinicio y Wake-on-LAN no están implementados. El agente no arranca automáticamente al volver a encender salvo que hayas configurado esa opción.

No se aceptan apagados sobre equipos desconectados u ocupados. La orden caduca si no se recoge pronto y su autorización final se consume una sola vez. Si se corta la red en un momento incierto, no se repite automáticamente. El bot distingue autorización de apagado físico: un equipo sin comunicación también puede haber perdido la red.

Puedes revocar este permiso con **Permisos-equipo.cmd**, desmarcando la casilla y reiniciando el agente. Solo afecta a nuevas operaciones, no puede cancelar una solicitud ya entregada a Windows.

Referencia de Windows: [shutdown](https://learn.microsoft.com/en-us/windows-server/administration/windows-commands/shutdown/). Un valor positivo de `/t` implica cierre forzado, por lo que este agente utiliza `/s /t 0` sin `/f`.
