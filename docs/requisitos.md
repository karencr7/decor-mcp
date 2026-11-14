# Requisitos - Decor MCP

## Descripción

Decor MCP es un servidor MCP de solo lectura («Decor Supabases») para Grupo Decor SAS. Permite que un colaborador de Comercial, Cartera, PQR o Mercadeo haga preguntas en lenguaje natural a su asistente de IA y reciba datos de la base de la empresa mediante 8 herramientas: business_guide, list_tables, describe_table, sample_rows, count_rows, list_distinct, query_table y query_analytics.

Cada consulta pasa por una política de acceso que solo permite SELECT/WITH, verifica las tablas autorizadas para el usuario y aplica límites de filas y de tiempo. Cada consulta, aceptada o denegada, queda registrada en auditoría. El MVP usa PostgreSQL local con datos ficticios. La conexión al Supabase real queda fuera de esta fase.

## Historias de usuario

### HU-01: Consultar cifras por oficina
Como colaborador comercial, quiero preguntar en lenguaje natural cuántas facturas emitió cada oficina en un mes, para obtener la cifra sin pedirla a TI.
- Dado un usuario con token comercial válido, cuando pide las facturas por oficina de septiembre de 2026, entonces recibe las cifras leídas de PostgreSQL con HTTP 200.
- Dado que la misma consulta se hace por REST y por el asistente, cuando se comparan los resultados, entonces las cifras coinciden.

Estado: Hecha

### HU-02: Bloquear escrituras
Como administrador de TI, quiero que cualquier intento de modificar datos sea rechazado, para que una consulta de la IA no cambie la base.
- Dado un token válido, cuando envía un DELETE, un WITH que contiene DELETE o un SELECT INTO, entonces recibe 403 con CONSULTA_NO_PERMITIDA y no se ejecuta nada.
- Dado el rol de base de datos de solo lectura, cuando intenta INSERT, UPDATE, DELETE o DDL, entonces PostgreSQL lo rechaza.

Estado: Hecha

### HU-03: Limitar tablas por usuario
Como colaborador comercial, quiero que la IA solo consulte las tablas que mi rol tiene autorizadas, para que no vea datos personales de clientes.
- Dado un token comercial, cuando pide nombres o correos de clientes, entonces la consulta es denegada y la IA no obtiene esos datos.
- Dado un token sin autorización sobre una tabla, cuando la consulta con query_table, entonces recibe 403.

Estado: Hecha

### HU-04: Auditar cada consulta
Como administrador de TI, quiero un registro de cada consulta aceptada o denegada, para saber quién consultó qué y cuándo.
- Dado una consulta por MCP, REST o contingencia, cuando termina, entonces queda en mcp.auditoria con usuario, canal, herramienta, resultado y duración.
- Dado un usuario que no es administrador, cuando pide GET /api/auditoria, entonces recibe 403.

Estado: Hecha

### HU-05: Seguir consultando sin IA
Como colaborador de Cartera, quiero elegir una consulta predefinida cuando el asistente no esté disponible, para no quedarme sin datos.
- Dado que no hay proveedor de IA disponible, cuando pide una de las 6 consultas de contingencia, entonces recibe el resultado con HTTP 200.
- Dado un identificador de consulta de contingencia que no existe, cuando lo pide, entonces recibe 404.

Estado: Hecha

### HU-06: Saber qué se puede preguntar
Como colaborador de PQR, quiero consultar la guía del negocio y las tablas disponibles, para formular preguntas que la base sí pueda responder.
- Dado un token válido, cuando pide la guía del negocio, entonces recibe business_guide con HTTP 200.
- Dado un token sin permiso sobre una tabla, cuando pide su estructura con describe_table, entonces recibe 403.

Estado: Hecha

### HU-07: Consultar sin saturar la base
Como administrador de TI, quiero que las consultas tengan límite de filas y de tiempo, para que el asistente no degrade la base.
- Dado una consulta de detalle, cuando el resultado supera 2.000 filas, entonces se devuelven como máximo 2.000.
- Dado una consulta analítica, cuando supera 500 filas o 15 segundos, entonces se corta.

Estado: Hecha

### HU-08: Usar el asistente desde una URL pública
Como colaborador comercial, quiero conectar mi asistente a una URL pública del servidor MCP, para no depender de un equipo con el servidor corriendo en localhost.
- Dado la URL pública del servidor MCP, cuando un cliente MCP se conecta con su token, entonces descubre las 8 herramientas.
- Dado la URL pública, cuando se hace GET /api/salud, entonces responde 200 con la conexión a PostgreSQL.

Estado: Pendiente

## No funcionales

| Atributo | Requisito medible | Verificación | Estado |
| --- | --- | --- | --- |
| Seguridad · Integridad | 0 escrituras ejecutadas; 100 % de los intentos de escritura reciben 403 | Colección Postman (casos DELETE, WITH…DELETE, SELECT INTO) | Hecha |
| Seguridad · Confidencialidad | 0 secretos en el repositorio; tokens guardados solo como hash SHA-256; credenciales en .env fuera de git | Revisión de .gitignore y escaneo del repositorio | Por verificar (escaneo) |
| Seguridad · Confidencialidad | 0 columnas personales en claro hacia el modelo en sample_rows, query_table y list_distinct | Revisión de vistas y políticas | Por verificar |
| Seguridad · Responsabilidad | 100 % de las llamadas quedan en mcp.auditoria | Revisión de la tabla de auditoría | Hecha |
| Disponibilidad (PROPUESTA) | La URL pública responde 200 en /api/salud durante toda la sustentación | Prueba de disponibilidad antes de la sustentación | Pendiente |
| Rendimiento (PROPUESTA) | Las consultas analíticas se cortan a más tardar a los 15 s | Prueba con consulta analítica que supere el límite | Por medir |

## Cambios frente a la IA

- **Eliminado:** un requisito de inicio de sesión con correo y clave, con bloqueo de 15 minutos tras 5 intentos fallidos. Decor MCP no tiene login de usuario: el acceso se hace con token Bearer, guardado como hash SHA-256. Se reemplazó por HU-03 (autorización por rol).
- **Movido a Won't:** notificaciones por correo (adaptador SMTP) y proveedor de IA alterno. Ambos están fuera del MVP según el Módulo 3; el supuesto 1 del Anexo A sigue sin confirmar.
- **Corregido el estado:** HU-08 aparece como Pendiente porque la API todavía corre en localhost. RNF de confidencialidad sobre columnas personales aparece como Por verificar porque no hay evidencia de que se haya probado.
