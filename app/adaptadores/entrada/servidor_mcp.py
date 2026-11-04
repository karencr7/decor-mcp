"""Adaptador de entrada «Servidor de herramientas MCP» (Figura 2, Tabla 8).

Expone las 8 herramientas de solo lectura por el Model Context Protocol
(JSON-RPC 2.0 sobre HTTP). Valida el token, convierte los parámetros y llama
al caso de uso. Los errores del dominio se devuelven como resultado con
isError=true y el motivo, para que la IA pueda corregir la consulta (Tabla 9).
"""

from __future__ import annotations

from typing import Any, Callable

import anyio
from mcp.server.mcpserver import Context, MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations

from app.aplicacion.autenticacion import Autenticador
from app.aplicacion.ejecutar_consulta import EjecutarConsulta
from app.dominio.errores import ErrorDecor
from app.dominio.modelos import Canal, TipoConsulta, Usuario

INSTRUCCIONES = (
    "Servidor MCP «Decor Supabases» (MVP con datos ficticios) para consultar en lenguaje natural "
    "los datos comerciales, de cartera, existencias, PQR y DecorClub de Grupo Decor. "
    "Llama SIEMPRE primero a business_guide para conocer las tablas permitidas, las claves de unión "
    "y las reglas del negocio (por ejemplo: un pedido no es una factura; en zventas netwr y erdat son texto). "
    "Todas las herramientas son de solo lectura. Usa query_analytics para agregados y query_table para detalle."
)

_SOLO_LECTURA = ToolAnnotations(read_only_hint=True, destructive_hint=False, idempotent_hint=True, open_world_hint=False)


def crear_servidor_mcp(caso_uso: EjecutarConsulta, autenticador: Autenticador) -> MCPServer:
    mcp = MCPServer(name="decor-supabases", title="Decor Supabases (MVP)", version="1.0.0",
                    instructions=INSTRUCCIONES)

    async def ejecutar(ctx: Context, accion: Callable[[Usuario], dict[str, Any]]) -> dict[str, Any]:
        """Autentica con el encabezado Authorization y ejecuta la acción fuera del
        hilo principal (las consultas a la base son bloqueantes)."""
        encabezados = ctx.headers or {}
        try:
            usuario = await anyio.to_thread.run_sync(autenticador.desde_encabezado, encabezados.get("authorization"))
            return await anyio.to_thread.run_sync(accion, usuario)
        except ErrorDecor as error:
            raise ToolError(f"[{error.codigo}] {error.mensaje}") from error

    @mcp.tool(annotations=_SOLO_LECTURA,
              description="Mapa del negocio y catálogo vivo de tablas permitidas para el usuario. Llamar al iniciar. "
                          "Si se envía 'table', devuelve el detalle de esa tabla.")
    async def business_guide(ctx: Context, table: str | None = None) -> dict[str, Any]:
        return await ejecutar(ctx, lambda u: caso_uso.guia_negocio(u, Canal.MCP, table))

    @mcp.tool(annotations=_SOLO_LECTURA, description="Lista las tablas permitidas y sus columnas comentadas.")
    async def list_tables(ctx: Context) -> dict[str, Any]:
        return await ejecutar(ctx, lambda u: caso_uso.listar_tablas(u, Canal.MCP))

    @mcp.tool(annotations=_SOLO_LECTURA, description="Columnas, tipos y descripciones de una tabla.")
    async def describe_table(ctx: Context, table: str) -> dict[str, Any]:
        return await ejecutar(ctx, lambda u: caso_uso.describir_tabla(u, Canal.MCP, table))

    @mcp.tool(annotations=_SOLO_LECTURA, description="Muestra filas reales de una tabla (limit de 1 a 50).")
    async def sample_rows(ctx: Context, table: str, limit: int = 10) -> dict[str, Any]:
        return await ejecutar(ctx, lambda u: caso_uso.muestra_filas(u, Canal.MCP, table, limit))

    @mcp.tool(annotations=_SOLO_LECTURA,
              description="Conteo rápido de filas de una tabla, con filtro de igualdad opcional (column = value).")
    async def count_rows(ctx: Context, table: str, column: str | None = None, value: str | None = None) -> dict[str, Any]:
        return await ejecutar(ctx, lambda u: caso_uso.contar_filas(u, Canal.MCP, table, column, value))

    @mcp.tool(annotations=_SOLO_LECTURA, description="Valores distintos de una columna y su frecuencia (máximo 200).")
    async def list_distinct(ctx: Context, table: str, column: str) -> dict[str, Any]:
        return await ejecutar(ctx, lambda u: caso_uso.valores_distintos(u, Canal.MCP, table, column))

    @mcp.tool(annotations=_SOLO_LECTURA,
              description="Consulta SQL de DETALLE (solo SELECT/WITH sobre tablas permitidas). Máximo 2.000 filas.")
    async def query_table(ctx: Context, sql: str) -> dict[str, Any]:
        return await ejecutar(ctx, lambda u: caso_uso.consultar_sql(u, Canal.MCP, sql, TipoConsulta.DETALLE))

    @mcp.tool(annotations=_SOLO_LECTURA,
              description="Consulta SQL de AGREGADOS (GROUP BY, SUM, COUNT; solo SELECT/WITH). "
                          "Máximo 500 filas y 15 segundos. Filtra siempre por fecha.")
    async def query_analytics(ctx: Context, sql: str) -> dict[str, Any]:
        return await ejecutar(ctx, lambda u: caso_uso.consultar_sql(u, Canal.MCP, sql, TipoConsulta.ANALITICA))

    return mcp
