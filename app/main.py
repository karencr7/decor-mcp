"""Punto de entrada: arma el hexágono (inyección de dependencias por constructor)
y publica dos adaptadores de entrada sobre el mismo caso de uso:

    /mcp     -> Servidor de herramientas MCP (para Claude, Copilot u otro cliente MCP)
    /api/... -> API REST (Postman, Swagger y modo de contingencia)
    /docs    -> Documentación OpenAPI (Swagger UI)

Ejecutar en local:  uvicorn app.main:app --reload
"""

from __future__ import annotations

from contextlib import asynccontextmanager

import psycopg
from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from mcp.server.transport_security import TransportSecuritySettings

from app.adaptadores.entrada.api_rest import registrar_api
from app.adaptadores.entrada.servidor_mcp import crear_servidor_mcp
from app.adaptadores.salida.postgres import (
    RegistroAuditoriaPostgres, RepositorioDatosPostgres, RepositorioUsuariosPostgres,
)
from app.aplicacion.autenticacion import Autenticador
from app.aplicacion.consultas_predefinidas import ModoContingencia
from app.aplicacion.ejecutar_consulta import EjecutarConsulta
from app.config import Configuracion, obtener_configuracion
from app.dominio.politica_acceso import PoliticaAcceso

DESCRIPCION = """
**MVP del servidor MCP «Decor Supabases»** · Grupo Decor SAS (datos **ficticios**).

Asistente de consulta en lenguaje natural: la IA (Claude, Copilot u otro cliente MCP) usa
8 herramientas de **solo lectura** expuestas en `/mcp`. Esta API REST expone las mismas
operaciones para pruebas y para el **modo de contingencia** (consultas predefinidas sin IA).

**Autenticación:** botón *Authorize* → pega el token del usuario (variables `DECOR_TOKEN_*` del `.env`).
"""


def crear_app(config: Configuracion | None = None) -> FastAPI:
    config = config or obtener_configuracion()

    # Adaptadores de salida
    repositorio = RepositorioDatosPostgres(config.db_lector_url, config.catalogo_ttl_s)
    usuarios = RepositorioUsuariosPostgres(config.db_app_url)
    auditoria = RegistroAuditoriaPostgres(config.db_app_url)

    # Núcleo
    caso_uso = EjecutarConsulta(repositorio, auditoria, PoliticaAcceso())
    contingencia = ModoContingencia(caso_uso)
    autenticador = Autenticador(usuarios)

    # Adaptador de entrada MCP
    mcp = crear_servidor_mcp(caso_uso, autenticador)
    hosts = [h.strip() for h in config.mcp_hosts_permitidos.split(",") if h.strip()]
    mcp_app = mcp.streamable_http_app(
        streamable_http_path="/mcp",
        stateless_http=True,
        json_response=True,
        transport_security=TransportSecuritySettings(
            enable_dns_rebinding_protection=True,
            allowed_hosts=hosts,
            allowed_origins=[f"http://{h}" for h in hosts] + [f"https://{h}" for h in hosts],
        ),
    )

    @asynccontextmanager
    async def ciclo_de_vida(_: FastAPI):
        async with mcp.session_manager.run():
            yield

    app = FastAPI(title="Decor MCP · API", version="1.0.0", description=DESCRIPCION, lifespan=ciclo_de_vida)

    def verificar_bd() -> bool:
        try:
            with psycopg.connect(config.db_lector_url, connect_timeout=3) as conn:
                conn.execute("SELECT 1")
            return True
        except psycopg.Error:
            return False

    @app.get("/", include_in_schema=False)
    def inicio() -> RedirectResponse:
        return RedirectResponse("/docs")

    registrar_api(app, caso_uso, contingencia, autenticador, auditoria, verificar_bd)

    # Se monta al final para que las rutas /api y /docs tengan prioridad.
    app.mount("/", mcp_app)
    return app


app = crear_app()
