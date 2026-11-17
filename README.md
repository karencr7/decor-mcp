# Decor MCP · Asistente de consulta en lenguaje natural (MVP)

[![CI](https://github.com/karencr7/decor-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/karencr7/decor-mcp/actions/workflows/ci.yml)

MVP del **servidor MCP «Decor Supabases»** diseñado en el Módulo 2 (*Propuesta arquitectónica Grupo Decor*).
Un colaborador le pregunta a una IA, en español, algo como *«¿cuántas facturas emitió cada oficina en septiembre?»*,
y la IA responde con datos de la base usando **8 herramientas de solo lectura** que expone este servidor.

> **Datos ficticios.** La base incluida reproduce la estructura de 13 tablas de Grupo Decor (Figura 4 de la propuesta),
> pero **todos los datos son inventados** (`database/generar_datos_ficticios.py`). No se usa ni se publica información real
> de la empresa ni de sus clientes (Ley 1581 de 2012).

**Autoras:** Karen Eliana Caicedo · María José Vargas — Diplomado en Ingeniería de Software Asistida por IA, Universidad Santiago de Cali, Módulo 3.

   | Integrante | Aporte principal |
   |---|---|
   | Karen Eliana Caicedo | Configuración del entorno, ejecución en Docker, pruebas en Swagger/Postman e integración con Copilot |
   | María José Vargas | Revisión del diseño, documentación del uso de IA y revisión del Pull Request |
   
---

## 1. Qué está implementado

| Caso de uso / requisito del diseño | Estado | Dónde |
|---|---|---|
| **CU principal: «Ejecutar consulta»** (pregunta → herramienta → política → datos → auditoría) | ✅ Implementado | `app/aplicacion/ejecutar_consulta.py` |
| 8 herramientas MCP (Tabla 8): `business_guide`, `list_tables`, `describe_table`, `sample_rows`, `count_rows`, `list_distinct`, `query_table`, `query_analytics` | ✅ | `app/adaptadores/entrada/servidor_mcp.py` |
| Política de acceso: solo SELECT/WITH, tablas por usuario (`mcp_permisos`), 2.000 filas / 500 filas y 15 s | ✅ | `app/dominio/politica_acceso.py` |
| Registro de auditoría (quién, qué, cuándo, canal, resultado) | ✅ | tabla `mcp.auditoria` |
| Modo de contingencia sin IA (6 consultas predefinidas de la Tabla 13) | ✅ | `app/aplicacion/consultas_predefinidas.py` |
| Integración con IA (cliente MCP: GitHub Copilot en VS Code; compatible con Claude) | ✅ | `.vscode/mcp.json` |
| API REST documentada (OpenAPI/Swagger) + colección Postman | ✅ | `/docs`, `postman/` |
| Docker y Docker Compose, configuración por variables de entorno | ✅ | `Dockerfile`, `docker-compose.yml`, `.env.example` |
| Notificaciones por correo (Adaptador SMTP) | ⏳ Pendiente | Supuesto por validar (Anexo A, punto 1) |
| Proveedor de IA alterno automático (nivel 1 de la Tabla 12) | ⏳ Pendiente | MCP lo permite: otro cliente apunta al mismo `/mcp` |
| Conexión al Supabase real de Grupo Decor | ⏳ Fuera del MVP | Requiere autorización de TI y contrato de transmisión |

## 2. Arquitectura (hexagonal, igual a la Figura 2)

```
            ┌──────────── Adaptadores de ENTRADA ────────────┐
 IA (Copilot/Claude) ──MCP──▶ servidor_mcp.py   api_rest.py ◀──HTTP── Postman / Swagger / Contingencia
            └───────────────────────┬─────────────────────────┘
                                    ▼
                 ┌──────── NÚCLEO (no depende de tecnología) ────────┐
                 │  Caso de uso «EjecutarConsulta»                     │
                 │      │ aplica                                       │
                 │      ▼                                              │
                 │  Entidad «PoliticaAcceso»                           │
                 │  Puertos: RepositorioDatos · RegistroAuditoria ·    │
                 │           RepositorioUsuarios                       │
                 └───────────────────────┬─────────────────────────────┘
                                         ▼
            ┌──────────── Adaptadores de SALIDA (postgres.py) ───────┐
            │  RepositorioDatosPostgres (rol decor_lector, solo lectura) │
            │  RegistroAuditoriaPostgres · RepositorioUsuariosPostgres  │
            └───────────────────────────┬────────────────────────────┘
                                        ▼
                         PostgreSQL 16 (réplica local de Supabase)
```

| Carpeta | Capa | Responsabilidad |
|---|---|---|
| `app/dominio/` | Dominio | Entidades, errores y **Política de acceso**. No importa bases de datos, HTTP ni MCP. |
| `app/aplicacion/` | Aplicación | Caso de uso, modo de contingencia, autenticación y **puertos** (interfaces). |
| `app/adaptadores/entrada/` | Adaptadores de entrada | Servidor MCP (JSON-RPC) y API REST (FastAPI). Ambos usan el mismo caso de uso. |
| `app/adaptadores/salida/` | Adaptadores de salida | Implementación PostgreSQL de los puertos. Cambiar de base = cambiar este archivo. |
| `app/main.py` | Composición | Crea los objetos e inyecta dependencias por constructor. |
| `database/` | Datos | Esquema, datos ficticios y roles/permisos. |
| `tests/` | Pruebas | Unitarias (núcleo con dobles) e integración (PostgreSQL real, REST y MCP). |

**Seguridad en capas (defensa en profundidad):**
1. La **Política de acceso** analiza el SQL (con `sqlglot`) y rechaza escrituras, varias sentencias, `SELECT INTO`, `FOR UPDATE`,
   otros esquemas (`mcp`, `pg_catalog`, `information_schema`) y tablas no habilitadas para el usuario.
2. La base usa el rol **`decor_lector`**, que solo tiene `SELECT` y transacciones de solo lectura. Aunque la política fallara, la base rechaza cualquier escritura.
3. Cada consulta corre con `statement_timeout` y la base corta el resultado en el límite de filas.
4. Los tokens se guardan como **hash SHA-256**; las credenciales solo existen en `.env` (no versionado).

## 3. Tecnologías y justificación

| Tecnología | Uso | Por qué |
|---|---|---|
| Python 3.12 | Lenguaje | El **SDK oficial de MCP** es de referencia en Python y TypeScript; código legible y fácil de sustentar. |
| `mcp` 2.3 (SDK oficial) | Servidor MCP, transporte *Streamable HTTP* | Implementa el protocolo del diseño (ADR-01) sin reinventarlo. |
| FastAPI | API REST + OpenAPI/Swagger automático | Documentación de la API generada desde el código. |
| PostgreSQL 16 | Base de datos | Supabase **es** PostgreSQL: el SQL del diseño funciona igual (ADR-06). |
| psycopg 3 | Driver PostgreSQL | Consultas parametrizadas (evita inyección SQL). |
| sqlglot | Análisis de SQL | Permite a la Política de acceso entender el SQL en vez de buscar palabras. |
| Docker Compose | Contenedorización | Levanta base y API con un comando, igual en cualquier PC. |
| pytest, Postman/Newman | Pruebas | Pruebas automáticas y evidencia de la API. |

Las diferencias frente al diseño se explican en [`docs/decisiones-implementacion.md`](docs/decisiones-implementacion.md).

## 4. Instalación y ejecución (Windows, con Docker)

Requisitos: **Docker Desktop** (con "Engine running"), **Git** y **VS Code**.

```powershell
# 1. Clonar el repositorio y entrar a la carpeta
git clone https://github.com/<usuario>/decor-mcp.git
cd decor-mcp

# 2. Crear el archivo de configuración y cambiar sus valores
copy .env.example .env
notepad .env

# 3. Levantar base de datos + API
docker compose up --build
```

Cuando aparezca `Application startup complete`, abre:

| Qué | URL |
|---|---|
| Documentación interactiva (Swagger) | http://localhost:8000/docs |
| Estado del servicio | http://localhost:8000/api/salud |
| Endpoint MCP (para la IA) | http://localhost:8000/mcp |

Para detener: `Ctrl + C` y luego `docker compose down`. Para **borrar la base** y recrearla desde los scripts: `docker compose down -v`.

> Si cambias valores del `.env` **después** del primer arranque, ejecuta `docker compose down -v` para que la base se cree de nuevo con los nuevos valores.

### Variables de entorno

| Variable | Uso |
|---|---|
| `POSTGRES_USER`, `POSTGRES_PASSWORD` | Superusuario de PostgreSQL (solo para crear la base) |
| `DECOR_DB_LECTOR_PASSWORD` | Clave del rol de solo lectura `decor_lector` |
| `DECOR_DB_APP_PASSWORD` | Clave del rol `decor_app` (usuarios, permisos, auditoría) |
| `DECOR_TOKEN_ADMIN`, `DECOR_TOKEN_COMERCIAL`, `DECOR_TOKEN_CARTERA` | Tokens de los 3 usuarios de demostración |
| `DECOR_DB_LECTOR_URL`, `DECOR_DB_APP_URL` | Las arma Docker Compose; solo se definen a mano si se ejecuta sin Docker |

### Usuarios de demostración

| Usuario | Token (`.env`) | Tablas habilitadas |
|---|---|---|
| `admin@decor-demo.co` | `DECOR_TOKEN_ADMIN` | Las 14 tablas de negocio + ver auditoría |
| `comercial@decor-demo.co` | `DECOR_TOKEN_COMERCIAL` | `zventas`, `mv_zpedidos`, `zeentregas`, `mm_maestros`, existencias, `dv_meta` (sin datos personales) |
| `cartera@decor-demo.co` | `DECOR_TOKEN_CARTERA` | `zfi_job_cartera`, `zventas`, `dv_meta` |

Agregar una tabla a un usuario es insertar una fila en `mcp.permisos`; no hay que redesplegar (ADR-04).

## 5. Endpoints

Detalle completo, ejemplos y códigos en [`docs/api.md`](docs/api.md) y en Swagger (`/docs`).

| Método | Ruta | Herramienta | Códigos |
|---|---|---|---|
| POST | `/mcp` | **Endpoint MCP** (JSON-RPC 2.0: `initialize`, `tools/list`, `tools/call`) | 200 (errores de herramienta con `isError: true`) |
| GET | `/api/salud` | Estado del servicio | 200 |
| GET | `/api/guia` | `business_guide` | 200, 401 |
| GET | `/api/tablas` | `list_tables` | 200, 401 |
| GET | `/api/tablas/{tabla}` | `describe_table` | 200, 401, 403, 404 |
| GET | `/api/tablas/{tabla}/muestra?limite=` | `sample_rows` | 200, 400, 401, 403 |
| GET | `/api/tablas/{tabla}/conteo?columna=&valor=` | `count_rows` | 200, 400, 401, 403 |
| GET | `/api/tablas/{tabla}/distintos?columna=` | `list_distinct` | 200, 400, 401, 403 |
| POST | `/api/consultas/detalle` | `query_table` (2.000 filas) | 200, 400, 401, 403, 408 |
| POST | `/api/consultas/analitica` | `query_analytics` (500 filas, 15 s) | 200, 400, 401, 403, 408 |
| GET | `/api/contingencia/consultas` | Catálogo de consultas predefinidas | 200, 401 |
| POST | `/api/contingencia/consultas/{id}` | Ejecutar consulta predefinida | 200, 400, 401, 403, 404 |
| GET | `/api/auditoria?limite=` | Registro de auditoría (solo admin) | 200, 401, 403 |

## 6. Integración con IA (GitHub Copilot en VS Code)

1. Con el proyecto corriendo (`docker compose up`), abre la carpeta del proyecto en VS Code.
2. Abre `.vscode/mcp.json`: encima de `"decor-supabases"` aparece **Start**. Haz clic y pega un token (por ejemplo `DECOR_TOKEN_COMERCIAL`).
3. Abre **Copilot Chat**, elige el modo **Agent** y verifica en el ícono de herramientas 🛠 que aparezcan las 8 herramientas de `decor-supabases`.
4. Pregunta, por ejemplo:
   - *¿Cuántas facturas emitió cada oficina en septiembre de 2026?*
   - *¿Cuántos pedidos están abiertos y cuánto suman?*
   - *¿Cuál es el material con más existencias en Decorcerámica?*
   - *Muéstrame el correo de los clientes* → con el token comercial **debe ser rechazado** (tabla no autorizada).
5. Copilot pide permiso antes de ejecutar cada herramienta (control «visibilidad de cada llamada», Tabla 11).
6. Revisa la auditoría con el token admin en `GET /api/auditoria`: cada llamada de la IA queda registrada con canal `MCP`.

El servidor es MCP estándar, así que también funciona con **Claude** u otro cliente MCP apuntando a `http://localhost:8000/mcp`
con el encabezado `Authorization: Bearer <token>` (estrategia de sustitución, Tabla 14).

## 6.1 Asistente con IA integrado (Groq) · Módulo 6

Además del cliente MCP externo, la API trae su **propia función con IA**: `POST /api/asistente/preguntar` y una página de demo en **`/asistente`**.
El LLM de [Groq](https://console.groq.com) (`openai/gpt-oss-120b`, configurable con `DECOR_GROQ_MODELO`) recibe la pregunta y las 8 herramientas como *tool calling*; cada herramienta
se ejecuta con el **mismo caso de uso**, así que la Política de acceso, los límites y la auditoría (canal `ASISTENTE_IA`) se aplican igual. El LLM nunca toca la base.

| Situación | Respuesta |
|---|---|
| Pregunta válida | `200` con `respuesta`, `herramientas_usadas` y `modelo` |
| Sin token / token inválido | `401` |
| Pregunta vacía o de más de 500 caracteres | `422` |
| Sin `GROQ_API_KEY`, Groq caído o límite de uso | `503` con sugerencia de usar el modo de contingencia |

La llave va **solo** en la variable `GROQ_API_KEY` (archivo `.env` o panel de Render); nunca en el repositorio.
Código: `app/aplicacion/asistente.py`, `app/adaptadores/salida/groq.py`, `app/adaptadores/entrada/api_asistente.py`.

## 6.2 Despliegue público (Render, plan gratuito)

1. En [render.com](https://render.com) → **New → Blueprint** → elegir este repositorio. Render lee `render.yaml`.
2. Render genera las claves y los tokens. En **Environment**, pegar la llave en `GROQ_API_KEY`.
3. Esperar el despliegue y abrir `https://<servicio>.onrender.com/docs` y `/asistente`.
4. Los tokens de demostración se ven en **Environment** (`DECOR_TOKEN_COMERCIAL`, etc.).

La imagen `Dockerfile.render` levanta PostgreSQL 16 y la API en un solo contenedor (decisión en [ADR-002](docs/adr/ADR-002-base-de-datos-y-despliegue.md)).
El CI construye y prueba esa misma imagen en cada push. El plan gratuito se duerme tras 15 min: abrir la URL un minuto antes de la demo.

## 7. Pruebas

| Tipo | Cómo ejecutarlas | Resultado verificado |
|---|---|---|
| Unitarias + integración (pytest) | ver abajo | Corren en GitHub Actions en cada push (ver badge): unitarias con dobles + 8 de integración contra PostgreSQL real + colección Postman con Newman + imagen de Render |
| Colección Postman | Importar `postman/Decor_MCP.postman_collection.json`, poner los tokens en las variables y usar *Run collection* | 31 solicitudes, 37 verificaciones, 0 fallos |
| Cliente MCP oficial | `initialize` → `tools/list` → `tools/call` | 8 herramientas; errores de política devueltos con `isError: true` |

```powershell
# Pruebas unitarias (no necesitan base de datos)
docker compose run --rm --no-deps --user root -v ${PWD}/tests:/srv/tests api sh -c "pip install -q pytest httpx && python -m pytest -q tests"
```

Sin variables de base de datos, las 8 pruebas de integración se marcan como *skipped*.

## 8. Decisiones y pendientes

- Arquitectura C4 (contexto y contenedores): [`docs/arquitectura.md`](docs/arquitectura.md) · ADR del Módulo 6: [`docs/adr/`](docs/adr/)
- Requisitos (historias y criterios): [`docs/requisitos.md`](docs/requisitos.md)
- Manual de usuario (asistente, contingencia, administración y errores): [`docs/manual-usuario.md`](docs/manual-usuario.md)
- Decisiones de implementación (ADR-08 a ADR-12): [`docs/decisiones-implementacion.md`](docs/decisiones-implementacion.md)

## Implementación y pruebas del MVP
Se completa la implementación del MVP Decor MCP – Servidor MCP para Grupo Decor SAS, integrando las herramientas de consulta de información empresarial mediante lenguaje natural.

El desarrollo incluye:

Implementación de las 8 herramientas MCP para consultar y analizar información de PostgreSQL.
Implementación de la política de acceso con validación de tokens, permisos por usuario y restricciones de consultas de solo lectura.
Integración de FastAPI para exponer los servicios REST.
Implementación del registro de auditoría para consultas permitidas y rechazadas.
Configuración de Docker y Docker Compose para facilitar el despliegue.
Integración con GitHub Copilot como cliente MCP.
Ejecución de pruebas automatizadas con Postman, obteniendo 37 pruebas aprobadas y 0 fallidas.

Se valida el funcionamiento integral de la solución, incluyendo la conexión a PostgreSQL, la seguridad de las consultas, la persistencia de auditoría y la interacción con IA.

Estado: Implementación integrada y verificada correctamente.
- Uso responsable de IA en el desarrollo: [`docs/uso-de-ia.md`](docs/uso-de-ia.md)
- Pendientes: adaptador SMTP, proveedor de IA alterno automático, pool de conexiones, autenticación corporativa (SSO) en lugar de tokens, conexión al Supabase real con autorización de TI.
