# ADR-002: PostgreSQL 16 con datos ficticios y despliegue en Render (Docker)

- **Estado:** Aceptada (Módulo 6)
- **Relacionada con:** ADR-06 (Módulo 2) y ADR-09 de [decisiones-implementacion.md](../decisiones-implementacion.md)

## Contexto

Grupo Decor guarda sus datos en **Supabase** (PostgreSQL). El proyecto se publica en GitHub y se presenta
en clase, y 9 de las tablas contienen datos personales (Ley 1581 de 2012), así que no se puede usar la base
real. Además, para la sustentación se necesita una **URL pública gratuita** donde funcionen la API, el
endpoint MCP y el asistente con IA.

## Decisión

1. Usar **PostgreSQL 16** con la misma estructura de tablas y **datos ficticios** (`database/`).
2. Desplegar en **Render (plan gratuito)** con un solo servicio Docker (`Dockerfile.render`) que contiene
   PostgreSQL y la API. Al arrancar, el contenedor crea la base con los mismos scripts de `database/`,
   y luego inicia uvicorn. La configuración está en `render.yaml` (Blueprint).

## Alternativas consideradas

1. **Supabase gratuito + Render para la API:** más parecido a producción, pero exige cargar 230 KB de datos
   a mano, traducir `03_seguridad.sh` y usar el *pooler* IPv4. Más pasos y más puntos de falla para la demo.
2. **Railway / Fly.io:** sirven, pero ya no tienen un plan gratuito permanente sin tarjeta.

## Consecuencias

- ✅ Un solo clic para desplegar desde GitHub; las claves y tokens los genera Render (`generateValue`).
- ✅ El mismo SQL funciona en Supabase cambiando solo `DECOR_DB_LECTOR_URL` y `DECOR_DB_APP_URL`.
- ⚠️ La base es **efímera**: cada reinicio recrea los datos y borra la auditoría. Aceptable para una demo.
- ⚠️ El plan gratuito se "duerme" tras 15 min sin tráfico: abrir la URL ~1 minuto antes de sustentar.
- ⚠️ No apto para producción: allí la base debe ser el Supabase de TI, separado de la API.
