# API del servidor Decor MCP

Hay dos formas de usar el servidor, y las dos llaman al **mismo caso de uso** («Ejecutar consulta»):

1. **Endpoint MCP** `POST /mcp`, para la IA (JSON-RPC 2.0, transporte *Streamable HTTP*).
2. **API REST** `/api/...`, para Postman, Swagger y el modo de contingencia.

La documentación interactiva OpenAPI está en **http://localhost:8000/docs**.

**Autenticación:** todas las rutas, excepto `/api/salud`, requieren el encabezado `Authorization: Bearer <token>`.

> Los ejemplos de respuesta de este documento son **respuestas reales** obtenidas con los datos ficticios de `database/02_datos_ficticios.sql`.

---

## 1. Endpoint MCP (`POST /mcp`)

Encabezados: `Content-Type: application/json`, `Accept: application/json, text/event-stream`, `Authorization: Bearer <token>`.

| Herramienta | Parámetros | Límite |
|---|---|---|
| `business_guide` | `table` (opcional) | — |
| `list_tables` | — | — |
| `describe_table` | `table` | 1 tabla |
| `sample_rows` | `table`, `limit` | 1 a 50 filas |
| `count_rows` | `table`, `column` (opcional), `value` (opcional) | — |
| `list_distinct` | `table`, `column` | 200 valores |
| `query_table` | `sql` (SELECT/WITH) | 2.000 filas |
| `query_analytics` | `sql` (SELECT/WITH) | 500 filas · 15 s |

**Ejemplo `tools/call`:**

```json
{"jsonrpc": "2.0", "id": 7, "method": "tools/call",
 "params": {"name": "count_rows", "arguments": {"table": "mv_zpedidos", "column": "gbstk", "value": "A"}}}
```

Respuesta:

```json
{"jsonrpc": "2.0", "id": 7, "result": {
  "content": [{"type": "text", "text": "{\"tabla\": \"mv_zpedidos\", \"filtro\": {\"gbstk\": \"A\"}, \"total\": 117}"}],
  "structuredContent": {"tabla": "mv_zpedidos", "filtro": {"gbstk": "A"}, "total": 117},
  "isError": false}}
```

**Error de ejecución** (Tabla 9 de la propuesta): la política rechaza la operación y la IA recibe el motivo para corregirla.

```json
{"jsonrpc": "2.0", "id": 9, "result": {"isError": true, "content": [{"type": "text",
  "text": "Error executing tool query_table: [CONSULTA_NO_PERMITIDA] Solo se permiten consultas SELECT o WITH (solo lectura)."}]}}
```

Los errores de protocolo (herramienta desconocida, parámetros con tipo incorrecto) se devuelven como objeto `error` de JSON-RPC.

---

## 2. API REST

### Códigos HTTP implementados

| Código | Cuándo | Cuerpo |
|---|---|---|
| 200 | Consulta correcta | Resultado |
| 400 | SQL mal escrito, columna inexistente, parámetro fuera de rango | `{"error": "PARAMETRO_INVALIDO" \| "ERROR_EJECUCION", "mensaje": "..."}` |
| 401 | Falta el token o es inválido | `{"error": "NO_AUTENTICADO", ...}` |
| 403 | Escritura, tabla no habilitada, esquema interno, auditoría sin ser admin | `{"error": "CONSULTA_NO_PERMITIDA" \| "TABLA_NO_AUTORIZADA" \| "SOLO_ADMIN", ...}` |
| 404 | Tabla o consulta predefinida inexistente | `{"error": "NO_ENCONTRADO", ...}` |
| 408 | La consulta superó el tiempo máximo | `{"error": "TIEMPO_AGOTADO", ...}` |
| 422 | Cuerpo JSON con estructura incorrecta (validación de FastAPI) | detalle de validación |
| 503 | La base de datos no responde | `{"error": "SERVICIO_NO_DISPONIBLE", ...}` |

### Formato de resultado de consulta

```json
{"columnas": ["vkbur", "facturas"],
 "filas": [{"vkbur": "BOG1", "facturas": 15}, {"vkbur": "MED1", "facturas": 13},
           {"vkbur": "CAL1", "facturas": 9}, {"vkbur": "BAQ1", "facturas": 7}],
 "total_filas": 4, "truncado": false, "limite_aplicado": 500}
```

`truncado: true` indica que había más filas que el límite permitido.

### Rutas

#### `GET /api/salud`
Sin autenticación. `200 {"estado": "ok", "base_datos": "ok"}`.

#### `GET /api/guia?tabla=`
`business_guide`. Devuelve usuario, reglas de negocio, claves de unión, preguntas frecuentes, tablas permitidas, límites y fecha de última carga.

#### `GET /api/tablas` · `GET /api/tablas/{tabla}`
`list_tables` y `describe_table`. 403 si la tabla no está habilitada para el usuario.

#### `GET /api/tablas/{tabla}/muestra?limite=10`
`sample_rows`. `limite` de 1 a 50 (400 fuera de rango).

#### `GET /api/tablas/{tabla}/conteo?columna=&valor=`
`count_rows`. Ejemplo real: `GET /api/tablas/mv_zpedidos/conteo?columna=gbstk&valor=A` → `{"tabla": "mv_zpedidos", "filtro": {"gbstk": "A"}, "total": 117}`.

#### `GET /api/tablas/{tabla}/distintos?columna=`
`list_distinct`. Máximo 200 valores con su frecuencia.

#### `POST /api/consultas/detalle` · `POST /api/consultas/analitica`
`query_table` (2.000 filas) y `query_analytics` (500 filas, 15 s). Cuerpo:

```json
{"sql": "SELECT vkbur, COUNT(DISTINCT vbeln) AS facturas FROM zventas WHERE erdat BETWEEN '20260901' AND '20260930' GROUP BY vkbur ORDER BY facturas DESC"}
```

Error real con SQL mal escrito (`400`):
```json
{"error": "PARAMETRO_INVALIDO", "mensaje": "SQL inválido cerca de la línea 1, columna 17. Revisa la sintaxis de PostgreSQL."}
```

#### `GET /api/contingencia/consultas`
Catálogo de las 6 consultas predefinidas (Tabla 13): `facturacion-oficina-mes`, `cartera-vencida-cliente`, `existencias-material`, `pedidos-estado`, `pqr-oficina`, `puntos-decorclub`, con sus parámetros y ejemplos.

#### `POST /api/contingencia/consultas/{id}`
Cuerpo `{"parametros": {"oficina": "BOG1", "mes": "202609"}}`. Respuesta real:

```json
{"consulta": "facturacion-oficina-mes", "titulo": "Facturación por oficina y mes",
 "parametros": {"oficina": "BOG1", "mes": "202609"},
 "columnas": ["oficina", "facturas", "valor_neto"],
 "filas": [{"oficina": "BOG1", "facturas": 15, "valor_neto": 365639100.0}],
 "total_filas": 1, "truncado": false, "limite_aplicado": 500,
 "ultima_carga_datos": "2026-10-31T23:30:00+00:00"}
```

#### `GET /api/auditoria?limite=50`
Solo administrador (403 para los demás). Cada registro: `fecha`, `correo`, `canal` (`MCP`, `REST`, `CONTINGENCIA`), `herramienta`, `detalle`, `tablas`, `resultado` (`OK`, `DENEGADA`, `ERROR`), `motivo`, `filas`, `duracion_ms`.
