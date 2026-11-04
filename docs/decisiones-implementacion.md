# Decisiones de implementación (Módulo 3)

Continúan el registro ADR de la propuesta del Módulo 2 (Tabla 10, ADR-01 a ADR-07, todos se mantienen).
Aquí se registran las decisiones tomadas al construir el MVP y las **diferencias entre el diseño y la implementación**.

| ADR | Decisión | Contexto | Alternativas descartadas | Consecuencias |
|---|---|---|---|---|
| 08 | Implementar el servidor MCP en **Python con el SDK oficial `mcp`** y FastAPI | El SDK oficial (Python/TypeScript) implementa el protocolo y el transporte *Streamable HTTP*; FastAPI genera OpenAPI automáticamente | Java/Spring Boot (visto en clase): su soporte MCP depende de librerías adicionales; implementar JSON-RPC a mano | Menos código propio de protocolo; el núcleo sigue siendo independiente del framework |
| 09 | Base **PostgreSQL 16 local con datos ficticios** en lugar del Supabase real | El código va a un repositorio y se presenta en clase; 9 tablas tienen datos personales (Ley 1581) | Conectar al Supabase real; usar MySQL | Sin riesgo legal ni de fuga; el mismo SQL de PostgreSQL funciona en Supabase cambiando solo la URL de conexión |
| 10 | Exponer **también una API REST** con las mismas operaciones | La actividad pide API documentada y probada con Postman/Swagger; el modo de contingencia necesita una vía sin IA | Solo MCP | Dos adaptadores de entrada sobre el **mismo** caso de uso: las reglas se aplican igual en ambos |
| 11 | Identificar al usuario con **token Bearer** (hash SHA-256 en `mcp.usuarios`) | `business_guide` debe calcular el catálogo por usuario y la auditoría debe saber quién consultó | Sin autenticación; SSO corporativo | Simple y seguro para el MVP; en producción se reemplaza por SSO/OAuth de Grupo Decor |
| 12 | **Defensa en profundidad**: Política de acceso (análisis del SQL) + rol de base de solo lectura + `statement_timeout` | La seguridad debe estar en el servidor y no en el modelo (Conclusiones del Módulo 2) | Solo validar texto con expresiones regulares | Aunque una capa fallara, la otra impide escrituras o consultas excesivas |

## Diferencias entre diseño e implementación

| Elemento del diseño (Figura 2) | Implementación | Comentario |
|---|---|---|
| Adaptador Supabase | `RepositorioDatosPostgres` | Supabase es PostgreSQL; solo cambia la URL |
| Adaptador de registros / Almacén de registros | `RegistroAuditoriaPostgres` → tabla `mcp.auditoria` | Resuelve el supuesto 3 del Anexo A (dónde se guarda la auditoría) |
| Adaptador SMTP / Notificador de correo | No implementado | Supuesto 1 del Anexo A sin confirmar; se deja como pendiente |
| Tabla `mcp_permisos` | `mcp.permisos` (esquema interno `mcp`) | Separada del esquema de negocio para que nunca sea consultable |
| Modo de contingencia (C) | `/api/contingencia/...` | 6 consultas de la Tabla 13; misma Política de acceso; informa la última carga (`dv_meta`) |
| Tablero «Indicadores de gestión» (nivel 3) | No implementado | Fuera del alcance del MVP |
| Proveedor de IA (Anthropic) | Demostrado con GitHub Copilot como cliente MCP | El servidor es estándar; Claude se conecta al mismo `/mcp` (Tabla 14) |
| 27 tablas | 14 tablas de negocio | Las 13 de la Figura 4 + `dv_meta` |
