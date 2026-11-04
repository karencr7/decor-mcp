# Uso responsable de IA en el desarrollo

> **Completar con su experiencia real.** Este archivo es una base: ajústenlo con lo que ustedes hicieron, aceptaron y corrigieron.

## Herramientas de IA utilizadas

| Herramienta | Para qué se usó |
|---|---|
| Claude (Anthropic) | Análisis de la propuesta del Módulo 2, generación del código inicial, scripts SQL, Docker y documentación |
| GitHub Copilot (VS Code) | Cliente MCP para demostrar la integración: hace las preguntas en lenguaje natural usando las herramientas del servidor |

## Qué se aceptó, qué se corrigió y cómo se verificó

| Sugerencia de la IA | Decisión | Verificación |
|---|---|---|
| Usar datos ficticios en lugar del Supabase real | Aceptada (Ley 1581, repositorio público/compartido) | Revisión de `02_datos_ficticios.sql`: nombres, correos y documentos inventados |
| Validar el SQL con un analizador (`sqlglot`) en vez de buscar la palabra "SELECT" | Aceptada | Pruebas `tests/test_politica_acceso.py` con casos de ataque (`DELETE`, `WITH ... DELETE`, `SELECT INTO`, esquemas internos) |
| Rol de base de datos de solo lectura además de la política | Aceptada | Prueba manual: `DELETE` rechazado por la política y por la base |
 | La IA propuso inicialmente Java/Spring Boot; tras analizar el diseño recomendó Python con el SDK oficial de MCP | Aceptada | Se ejecutó el proyecto en Docker y la colección Postman pasó 37/37 pruebas |
   | Docker no instalaba por falta de "Virtual Machine Platform" | Corregido con wsl --install | Docker Desktop quedó en "Engine running" |
   | Conectar Copilot como cliente MCP | Aceptada | Copilot respondió facturas por oficina y negó el acceso a datos de clientes con el token comercial |

## Reglas que seguimos

- No se pegaron contraseñas, tokens ni datos reales de Grupo Decor en ninguna herramienta de IA.
- Ninguna funcionalidad se dio por terminada solo porque compilaba: se ejecutaron las pruebas (pytest y Postman).
- Ambas integrantes revisamos y podemos explicar cada capa del código.
