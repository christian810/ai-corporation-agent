# Control de sucursales desde la sede

## Arquitectura

La sede planifica y coordina; cada sucursal conserva una pasarela autenticada y sus permisos locales. Un agente local puede ser ligero (sin modelo) o usar Ollama y modelos permitidos. Los perfiles actuales ya permiten enviar encargos de texto a un modelo local y solicitar especialistas centrales. Todavía no hay descubrimiento automático ni comunicación entre procesos de agentes de terceros.

Cada empresa tendrá un catálogo de capacidades: diagnóstico, instalación, servicios, archivos empresariales y energía. Se habilitan por equipo. Las órdenes son estructuradas y auditables; ningún texto de Telegram o del modelo se convierte en shell arbitrario. Las credenciales de cada empresa y equipo permanecen separadas. Los equipos externos solo deben alcanzar el gateway 8443, no el panel administrativo. Las ACL de red se configuran expresamente antes de usar servidores ajenos.

## Diagnóstico de red (siguiente módulo)

Definir CIDR, equipos y puertos autorizados en la política local. Comprobar pertenencia a la lista antes de cada operación, sin aceptar rangos ampliados por el modelo. Empezar por conectividad, DNS e inventario explícito, con límites de concurrencia, duración y frecuencia. Registrar alcance y resultado; no intentar acceso mediante credenciales ni explorar redes ajenas. Una corrección de configuración será una operación distinta con aprobación y posibilidad de revertirla.

## Aplicaciones y servicios (módulos posteriores)

Catálogo de paquetes e instaladores oficiales con identificador, versión, firma o hash, parámetros fijos y permisos necesarios. Vista previa, ventana de mantenimiento, prueba y comprobación de salud después de instalar; plan de recuperación antes de cambiar un servicio. No descargar y ejecutar URLs arbitrarias ni elevar privilegios desde una respuesta de IA. Separar el agente ordinario de un ejecutor de administración con operaciones limitadas cuando haga falta elevación.

## Agentes locales

Cada perfil publica nombre, capacidades y modelos autorizados. La central envía trabajos al perfil y recibe resultados. El equipo local puede pedir ayuda a la central sin GPU. La elección de modelo local frente a central y los límites de gasto se definirán por empresa; no se decide automáticamente en función de un presupuesto todavía inexistente. Para redes, contabilidad y proyectos harán falta adaptadores de las aplicaciones concretas y permisos mínimos para cada una.

## Primer control operativo: apagado desde Telegram

El propietario identifica la empresa o equipo con /equipos y solicita /apagar EmpresaX, o /tarea apagar el equipo de EmpresaX. El bot presenta empresa, equipo y confirmación de un solo uso que caduca en dos minutos. Solo el propietario vinculado puede confirmar. La VM debe habilitar allow_shutdown de forma local y anunciar esa capacidad; si está desconectada, ocupada o no autorizada, no se crea el encargo.

El agente solo admite apagar su propio Windows, sin parámetros recibidos del usuario y sin cierre forzado de aplicaciones. El encargo tiene un plazo breve y nunca se repite automáticamente. La central registra la recepción y el envío de la orden; dejar de recibir latidos no demuestra que el hardware esté apagado. Reiniciar, despertar por red e instalar servicios quedan fuera de este primer control.

Referencia de Windows: https://learn.microsoft.com/en-us/windows-server/administration/windows-commands/shutdown/ . Un tiempo de espera positivo en shutdown implica cierre forzado; por eso el agente usará /s /t 0, sin /f. Guarda el trabajo antes de confirmar el apagado.
