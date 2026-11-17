# ADR-001: Python 3.12 + FastAPI + SDK oficial de MCP

- **Estado:** Aceptada (Módulo 3, se mantiene en el Módulo 6)
- **Relacionada con:** ADR-08 de [decisiones-implementacion.md](../decisiones-implementacion.md)

## Contexto

El MVP debe exponer herramientas de consulta para una IA usando el **Model Context Protocol** (MCP) y,
al mismo tiempo, una API REST documentada para Postman/Swagger y para el modo de contingencia sin IA.
El equipo es pequeño, tiene que sustentar cada línea del código y el tiempo de desarrollo es corto.

## Decisión

Usar **Python 3.12** con:

- el **SDK oficial `mcp`** para el servidor MCP (transporte *Streamable HTTP*);
- **FastAPI** para la API REST, porque genera la documentación OpenAPI (`/docs`) desde el código;
- arquitectura **hexagonal**: el núcleo (`app/dominio`, `app/aplicacion`) no importa FastAPI, MCP ni psycopg.

## Alternativas consideradas

1. **Java / Spring Boot** (visto en el diplomado): robusto, pero el soporte MCP depende de librerías
   adicionales y el código resultante es más extenso para un MVP.
2. **Node.js / TypeScript** con el SDK MCP de TypeScript: también es oficial, pero el equipo domina más
   Python y las librerías de análisis de SQL (sqlglot) son de Python.

## Consecuencias

- ✅ Menos código propio de protocolo: el SDK implementa JSON-RPC y el transporte.
- ✅ Swagger automático y validación de entradas con Pydantic.
- ✅ El núcleo se prueba con dobles, sin base de datos (pruebas unitarias rápidas).
- ⚠️ El SDK `mcp` cambia rápido: se fija la versión exacta en `requirements.txt`.
- ⚠️ Python es más lento que Java en CPU, irrelevante aquí porque el tiempo lo pone la base de datos.
