"""Adaptador de entrada REST (JSON) para pruebas con Postman/Swagger y para el
modo de contingencia (consultas predefinidas sin IA).

Expone las mismas operaciones que el servidor MCP y llama al MISMO caso de uso,
así que la Política de acceso y la auditoría se aplican igual por ambos canales.
"""

from typing import Annotated, Any, Callable

from fastapi import APIRouter, Depends, FastAPI, Query, Request
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

from app.aplicacion.autenticacion import Autenticador
from app.aplicacion.consultas_predefinidas import ModoContingencia
from app.aplicacion.ejecutar_consulta import EjecutarConsulta
from app.aplicacion.puertos import RegistroAuditoria
from app.dominio.errores import ErrorDecor, NoAutenticado
from app.dominio.modelos import Canal, TipoConsulta, Usuario

# Traducción de errores del dominio a códigos HTTP.
CODIGOS_HTTP = {
    "NO_AUTENTICADO": 401,
    "CONSULTA_NO_PERMITIDA": 403,
    "TABLA_NO_AUTORIZADA": 403,
    "PARAMETRO_INVALIDO": 400,
    "ERROR_EJECUCION": 400,
    "NO_ENCONTRADO": 404,
    "TIEMPO_AGOTADO": 408,
    "SERVICIO_NO_DISPONIBLE": 503,
}

_ERRORES_DOC = {
    400: {"description": "Parámetros o SQL inválidos"},
    401: {"description": "Falta el token o es inválido"},
    403: {"description": "Operación o tabla no permitida por la Política de acceso"},
}


class SolicitudSql(BaseModel):
    sql: str = Field(..., description="Sentencia SELECT o WITH",
                     examples=["SELECT vkbur, count(DISTINCT vbeln) AS facturas FROM zventas "
                               "WHERE erdat BETWEEN '20260901' AND '20260930' GROUP BY vkbur ORDER BY facturas DESC"])


class SolicitudPredefinida(BaseModel):
    parametros: dict[str, str] = Field(default_factory=dict, examples=[{"oficina": "BOG1", "mes": "202609"}])


class ErrorRespuesta(BaseModel):
    error: str
    mensaje: str


def registrar_api(app: FastAPI, caso_uso: EjecutarConsulta, contingencia: ModoContingencia,
                  autenticador: Autenticador, auditoria_registro: RegistroAuditoria,
                  verificar_bd: Callable[[], bool]) -> None:
    bearer = HTTPBearer(auto_error=False, description="Token del usuario (ver .env)")

    def usuario_actual(credenciales: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]) -> Usuario:
        if credenciales is None:
            raise NoAutenticado("Falta el encabezado 'Authorization: Bearer <token>'.")
        return autenticador.desde_encabezado(f"Bearer {credenciales.credentials}")

    Autenticado = Annotated[Usuario, Depends(usuario_actual)]

    @app.exception_handler(ErrorDecor)
    async def manejar_error(_: Request, error: ErrorDecor) -> JSONResponse:
        return JSONResponse(status_code=CODIGOS_HTTP.get(error.codigo, 500),
                            content={"error": error.codigo, "mensaje": error.mensaje})

    # ------------------------------------------------------------------ general
    general = APIRouter(prefix="/api", tags=["General"])

    @general.get("/salud", summary="Estado del servicio y de la base de datos")
    def salud() -> dict[str, Any]:
        return {"estado": "ok", "base_datos": "ok" if verificar_bd() else "no disponible"}

    @general.get("/guia", summary="business_guide: mapa del negocio y tablas permitidas", responses=_ERRORES_DOC)
    def guia(usuario: Autenticado, tabla: str | None = None) -> dict[str, Any]:
        return caso_uso.guia_negocio(usuario, Canal.REST, tabla)

    # ------------------------------------------------------------------ tablas
    tablas = APIRouter(prefix="/api/tablas", tags=["Herramientas de consulta"])

    @tablas.get("", summary="list_tables: tablas permitidas y columnas", responses=_ERRORES_DOC)
    def listar(usuario: Autenticado) -> dict[str, Any]:
        return caso_uso.listar_tablas(usuario, Canal.REST)

    @tablas.get("/{tabla}", summary="describe_table: columnas de una tabla",
                responses={**_ERRORES_DOC, 404: {"description": "La tabla no existe"}})
    def describir(usuario: Autenticado, tabla: str) -> dict[str, Any]:
        return caso_uso.describir_tabla(usuario, Canal.REST, tabla)

    @tablas.get("/{tabla}/muestra", summary="sample_rows: filas de ejemplo (1 a 50)", responses=_ERRORES_DOC)
    def muestra(usuario: Autenticado, tabla: str, limite: Annotated[int, Query(description="1 a 50")] = 10) -> dict[str, Any]:
        return caso_uso.muestra_filas(usuario, Canal.REST, tabla, limite)

    @tablas.get("/{tabla}/conteo", summary="count_rows: conteo con filtro opcional", responses=_ERRORES_DOC)
    def conteo(usuario: Autenticado, tabla: str, columna: str | None = None, valor: str | None = None) -> dict[str, Any]:
        return caso_uso.contar_filas(usuario, Canal.REST, tabla, columna, valor)

    @tablas.get("/{tabla}/distintos", summary="list_distinct: valores distintos y frecuencia", responses=_ERRORES_DOC)
    def distintos(usuario: Autenticado, tabla: str, columna: str) -> dict[str, Any]:
        return caso_uso.valores_distintos(usuario, Canal.REST, tabla, columna)

    # ------------------------------------------------------------------ consultas SQL
    consultas = APIRouter(prefix="/api/consultas", tags=["Herramientas de consulta"])

    @consultas.post("/detalle", summary="query_table: SQL de detalle (máx. 2.000 filas)",
                    responses={**_ERRORES_DOC, 408: {"description": "Tiempo agotado"}})
    def detalle(usuario: Autenticado, solicitud: SolicitudSql) -> dict[str, Any]:
        return caso_uso.consultar_sql(usuario, Canal.REST, solicitud.sql, TipoConsulta.DETALLE)

    @consultas.post("/analitica", summary="query_analytics: SQL de agregados (máx. 500 filas, 15 s)",
                    responses={**_ERRORES_DOC, 408: {"description": "Tiempo agotado"}})
    def analitica(usuario: Autenticado, solicitud: SolicitudSql) -> dict[str, Any]:
        return caso_uso.consultar_sql(usuario, Canal.REST, solicitud.sql, TipoConsulta.ANALITICA)

    # ------------------------------------------------------------------ contingencia
    cont = APIRouter(prefix="/api/contingencia", tags=["Modo de contingencia (sin IA)"])

    @cont.get("/consultas", summary="Catálogo de consultas predefinidas")
    def catalogo(usuario: Autenticado) -> list[dict[str, Any]]:
        return contingencia.listar()

    @cont.post("/consultas/{consulta_id}", summary="Ejecutar una consulta predefinida",
               responses={**_ERRORES_DOC, 404: {"description": "La consulta no existe"}})
    def ejecutar(usuario: Autenticado, consulta_id: str, solicitud: SolicitudPredefinida) -> dict[str, Any]:
        return contingencia.ejecutar(usuario, consulta_id, solicitud.parametros)

    # ------------------------------------------------------------------ administración
    admin = APIRouter(prefix="/api/auditoria", tags=["Administración"])

    @admin.get("", summary="Últimos registros de auditoría (solo administrador)", responses=_ERRORES_DOC)
    def auditoria(usuario: Autenticado, limite: Annotated[int, Query(ge=1, le=500)] = 50) -> Any:
        if not usuario.es_admin:
            return JSONResponse(status_code=403, content={"error": "SOLO_ADMIN",
                                                          "mensaje": "Solo el administrador puede ver la auditoría."})
        return auditoria_registro.ultimas(limite)

    for router in (general, tablas, consultas, cont, admin):
        app.include_router(router)
