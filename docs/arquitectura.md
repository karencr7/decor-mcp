# Arquitectura – Decor MCP

Documentación de la arquitectura con el **modelo C4** (niveles 1 y 2). Los diagramas están en Mermaid,
así que GitHub los dibuja y se versionan igual que el código. Los niveles 3 y 4 (componentes y código)
no se dibujan: la estructura hexagonal ya se ve en las carpetas de `app/` (ver sección 2 del README).

Decisiones de arquitectura: [ADR-001 · Stack](adr/ADR-001-stack.md) · [ADR-002 · Base de datos y despliegue](adr/ADR-002-base-de-datos-y-despliegue.md) ·
[ADR-08 a ADR-12 (Módulo 3)](decisiones-implementacion.md).

## Nivel 1 · Diagrama de contexto

Quién usa el sistema y con qué sistemas externos habla.

```mermaid
flowchart LR
    COL["👤 Colaborador de Grupo Decor<br/>(Comercial / Cartera)<br/>pregunta en español"]
    ADM["👤 Administrador TI<br/>gestiona permisos y revisa auditoría"]

    SYS["🟦 Decor MCP<br/>Servidor MCP + API REST de solo lectura<br/>(datos ficticios)"]

    IA["Cliente de IA (externo)<br/>GitHub Copilot en VS Code / Claude"]
    LLM["Proveedor LLM (externo)<br/>Groq · llama-3.3-70b-versatile"]
    DB[("Base de datos (externo)<br/>PostgreSQL 16<br/>réplica local de Supabase")]

    COL -->|"pregunta en el chat"| IA
    IA -->|"MCP · JSON-RPC sobre HTTPS + token Bearer"| SYS
    COL -->|"HTTPS · /api/asistente y contingencia"| SYS
    ADM -->|"HTTPS · /api/auditoria"| SYS
    SYS -->|"HTTPS + llave GROQ_API_KEY"| LLM
    SYS -->|"SQL de solo lectura"| DB
```

| Elemento | Tipo | Responsabilidad |
|---|---|---|
| Colaborador | Persona | Hace preguntas de negocio en lenguaje natural (facturas, pedidos, cartera, existencias). |
| Administrador TI | Persona | Habilita tablas por usuario (`mcp.permisos`) y revisa la auditoría. |
| Decor MCP | Sistema (este repo) | Expone 8 herramientas de solo lectura, aplica la Política de acceso y audita cada llamada. |
| Cliente de IA | Sistema externo | Copilot o Claude usan las herramientas por MCP. |
| Groq | Sistema externo | LLM que usa el asistente integrado (`/api/asistente/preguntar`) para elegir herramientas y redactar la respuesta. |
| PostgreSQL | Sistema externo | 14 tablas de negocio con datos ficticios + esquema interno `mcp`. |

## Nivel 2 · Diagrama de contenedores

Las piezas que se despliegan, con su tecnología y el protocolo de cada flecha.

```mermaid
flowchart TB
    subgraph Usuarios
        COP["Cliente MCP<br/>GitHub Copilot (VS Code)<br/>.vscode/mcp.json"]
        WEB["Navegador / Postman / Newman<br/>Swagger UI en /docs"]
    end

    subgraph DecorMCP["Decor MCP · contenedor Docker (python:3.12-slim + uvicorn)"]
        MCPS["Adaptador MCP<br/>SDK oficial mcp 2.3<br/>POST /mcp"]
        REST["Adaptador REST<br/>FastAPI · /api/*"]
        ASIS["Asistente IA<br/>POST /api/asistente/preguntar"]
        NUC["Núcleo<br/>Caso de uso EjecutarConsulta<br/>+ Política de acceso (sqlglot)"]
        PG["Adaptador de salida<br/>psycopg 3"]
    end

    DB[("PostgreSQL 16 · Docker<br/>esquema public (14 tablas, rol decor_lector)<br/>esquema mcp (usuarios, permisos, auditoría, rol decor_app)")]
    GROQ["Groq API<br/>api.groq.com/openai/v1"]

    COP -->|"HTTP(S) · JSON-RPC 2.0 · Bearer"| MCPS
    WEB -->|"HTTP(S) · JSON · Bearer"| REST
    WEB -->|"HTTP(S) · JSON · Bearer"| ASIS
    MCPS --> NUC
    REST --> NUC
    ASIS -->|"tool calling"| NUC
    ASIS -->|"HTTPS · chat/completions"| GROQ
    NUC --> PG
    PG -->|"TCP 5432 · SQL parametrizado · solo lectura"| DB
```

| Contenedor | Tecnología | Archivo |
|---|---|---|
| Adaptador MCP | SDK `mcp` 2.3, transporte Streamable HTTP | `app/adaptadores/entrada/servidor_mcp.py` |
| Adaptador REST | FastAPI + OpenAPI | `app/adaptadores/entrada/api_rest.py` |
| Asistente IA | `httpx` → Groq (API compatible con OpenAI) | `app/adaptadores/entrada/asistente_ia.py` |
| Núcleo | Python puro (sin dependencias de infraestructura) | `app/aplicacion/`, `app/dominio/` |
| Adaptador PostgreSQL | psycopg 3 | `app/adaptadores/salida/postgres.py` |
| Base de datos | PostgreSQL 16 (Docker) | `database/` |

## Verificación contra el código

Los diagramas se generaron con IA a partir de la estructura del proyecto y de `requirements.txt`, y luego se revisaron contra el código:

1. **Sin frontend propio.** La única interfaz web es Swagger UI (`/docs`); no se dibuja un contenedor "frontend" porque no existe en el repo.
2. **El cliente de IA nunca toca la base.** Toda consulta pasa por el servidor (Política de acceso + auditoría); por eso no hay flecha IA → base de datos.
3. **SMTP fuera del diagrama.** El notificador de correo está en el diseño del Módulo 2 pero no está implementado (pendiente en el README), así que no se muestra.
