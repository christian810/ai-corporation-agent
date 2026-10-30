# Sucursal ligera e IA en la sede central

## Actualizar una VM ya vinculada

1. Descarga el ZIP actualizado desde GitHub y extrae todos los archivos en la VM.
2. Detén el agente anterior (cierra su ventana Iniciar-agente.cmd). Si estaba oculto, reinicia la VM; si configuraste inicio automático, detén también ese proceso para evitar dos agentes.
3. Inicia sesión con el mismo usuario de Windows y conecta Tailscale.
4. Abre Iniciar-agente.cmd desde la carpeta nueva y deja la ventana abierta. Conserva config.json: no hace falta otra clave ni editar archivos.
5. En Corporaciones, el equipo debe indicar latido cada 5 s y sin comunicación tras 20 s. Las versiones anteriores conservan su plazo de 90 s hasta actualizarse. La interfaz refresca cada 2 s: un apagado puede tardar aproximadamente 22 s en reflejarse, con variaciones por red y carga. No distingue apagado, proceso detenido o fallo de red.

El latido funciona en un hilo independiente de los trabajos, incluidos avisos de Windows y consultas al modelo local. No mantiene un modelo cargado.

## Solicitar ayuda desde la sucursal

Abre Solicitar-ayuda.cmd. Escribe el encargo, elige Soporte, Red e infraestructura, Contabilidad o Proyectos y pulsa Pedir ayuda a la IA central. No se necesita Ollama, GPU ni modelos locales. La sede selecciona un especialista por área y usa su modelo central; devuelve texto, sin herramientas ni cambios en sistemas.

Primero puedes pulsar Prueba de ida y vuelta sin IA: la sede devolverá el texto recibido. Después prueba: «Propón tres comprobaciones sencillas para mejorar la red de una pequeña empresa. Solo recomendaciones, sin ejecutar cambios».

Las solicitudes aparecen en Corporaciones → Solicitudes de las sucursales a la sede. La misma solicitud se conserva para reintentar sin duplicarla tras un corte. Se procesan en el trabajador secuencial central cuando no tiene una tarea de plantilla lista. Pueden esperar si la sede está ocupada. Un reinicio que interrumpa la inferencia marca error y no la repite automáticamente.

Los resultados se guardan también en la carpeta local del agente como central-last-result.json; no publiques ese archivo ni central-pending.json. Cada equipo solo puede consultar sus propias peticiones. Límite del piloto: cinco pendientes por empresa y 200 solicitudes por equipo.

## Arquitectura prevista

- Sede: coordinación, especialistas, modelos, colas, aprobación del propietario e historial.
- Sucursal ligera: autenticación, latido, recepción de trabajos y envío de solicitudes. Sin inferencia local por defecto.
- Sucursal con recursos propios: puede habilitar modelos locales autorizados, conservando la opción de pedir ayuda a la central. No hay selección automática por presupuesto ni instalación automática de modelos en este piloto.
- Acciones: se incorporarán adaptadores concretos para inventario de red, proyectos y contabilidad con permisos por empresa. Una recomendación de IA no ejecuta cambios. No existe todavía shell remoto, acceso a documentos empresariales, routers, bancos o contabilidad real.

La distribución actual requiere Windows y Python: una placa con Linux necesita una distribución específica y un almacén de credenciales compatible, todavía no implementados. El gateway privado debe ser el único servicio accesible desde equipos de empresas ajenas; las reglas ACL de Tailscale deben impedir acceso al panel central. No se modifican esas reglas automáticamente.
