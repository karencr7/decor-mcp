"""Entidad «Política de acceso» (núcleo del hexágono, Figura 2).

Reglas (Tabla 11 y ADR 02, 03 y 04 de la propuesta):
  * Solo se aceptan sentencias SELECT o WITH, una por solicitud.
  * Solo se consultan tablas habilitadas para el usuario (mcp_permisos).
  * query_table devuelve máximo 2.000 filas; query_analytics máximo 500 filas
    y 15 segundos.
  * Las tablas de otros esquemas (mcp, pg_catalog, information_schema) nunca
    se exponen.

La seguridad vive aquí, en el servidor, y no en el modelo de IA: ninguna
instrucción que reciba la IA puede saltarse estas reglas.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

import sqlglot
from sqlglot import exp
from sqlglot.errors import ParseError

from app.dominio.errores import ConsultaNoPermitida, ParametroInvalido, TablaNoAutorizada
from app.dominio.modelos import TipoConsulta, Usuario

logging.getLogger("sqlglot").setLevel(logging.ERROR)  # silencia avisos del analizador SQL

_IDENTIFICADOR = re.compile(r"^[a-z_][a-z0-9_]{0,62}$")

# Nodos que nunca pueden aparecer, ni siquiera dentro de un WITH.
_NODOS_PROHIBIDOS = (
    exp.Insert, exp.Update, exp.Delete, exp.Merge, exp.Create, exp.Drop,
    exp.Alter, exp.Command, exp.Lock, exp.Copy, exp.Set, exp.Use,
)


@dataclass(frozen=True)
class SqlValidado:
    sql: str
    tablas: tuple[str, ...]


@dataclass(frozen=True)
class LimitesConsulta:
    max_filas: int
    tiempo_maximo_s: int


class PoliticaAcceso:
    LIMITE_DETALLE = 2000
    LIMITE_ANALITICA = 500
    TIEMPO_ANALITICA_S = 15
    TIEMPO_DETALLE_S = 30
    MAX_MUESTRA = 50
    MAX_DISTINTOS = 200

    # ------------------------------------------------------------------ límites
    def limites(self, tipo: TipoConsulta) -> LimitesConsulta:
        if tipo is TipoConsulta.ANALITICA:
            return LimitesConsulta(self.LIMITE_ANALITICA, self.TIEMPO_ANALITICA_S)
        return LimitesConsulta(self.LIMITE_DETALLE, self.TIEMPO_DETALLE_S)

    def validar_limite_muestra(self, limite: int) -> int:
        if not 1 <= limite <= self.MAX_MUESTRA:
            raise ParametroInvalido(f"El límite de la muestra debe estar entre 1 y {self.MAX_MUESTRA}.")
        return limite

    # ------------------------------------------------------------------ tablas
    def normalizar_identificador(self, nombre: str, que: str = "tabla") -> str:
        limpio = (nombre or "").strip().lower()
        if not _IDENTIFICADOR.match(limpio):
            raise ParametroInvalido(f"Nombre de {que} inválido: '{nombre}'.")
        return limpio

    def validar_tabla(self, usuario: Usuario, tabla: str) -> str:
        nombre = self.normalizar_identificador(tabla)
        if nombre not in usuario.tablas_autorizadas:
            raise TablaNoAutorizada(
                f"La tabla '{nombre}' no está habilitada para {usuario.correo}. "
                "Usa list_tables para ver las tablas permitidas."
            )
        return nombre

    # ------------------------------------------------------------------ SQL libre
    def validar_sql(self, usuario: Usuario, sql: str) -> SqlValidado:
        texto = (sql or "").strip().rstrip(";").strip()
        if not texto:
            raise ParametroInvalido("La consulta está vacía.")

        try:
            sentencias = [s for s in sqlglot.parse(texto, read="postgres") if s is not None]
        except ParseError as error:
            ubicacion = ""
            if error.errors:
                ubicacion = f" cerca de la línea {error.errors[0].get('line')}, columna {error.errors[0].get('col')}"
            raise ParametroInvalido(f"SQL inválido{ubicacion}. Revisa la sintaxis de PostgreSQL.") from error

        if len(sentencias) != 1:
            raise ConsultaNoPermitida("Solo se permite una sentencia por consulta.")
        sentencia = sentencias[0]

        if not isinstance(sentencia, exp.Query):
            raise ConsultaNoPermitida("Solo se permiten consultas SELECT o WITH (solo lectura).")
        for nodo in sentencia.walk():
            if isinstance(nodo, _NODOS_PROHIBIDOS):
                raise ConsultaNoPermitida("La consulta contiene operaciones de escritura o de control; solo se permite lectura.")
            if isinstance(nodo, exp.Select) and nodo.args.get("into") is not None:
                raise ConsultaNoPermitida("SELECT ... INTO crea tablas y no está permitido.")

        nombres_cte = {cte.alias_or_name.lower() for cte in sentencia.find_all(exp.CTE)}
        tablas: set[str] = set()
        for tabla in sentencia.find_all(exp.Table):
            nombre = (tabla.name or "").lower()
            esquema = (tabla.db or "").lower()
            if not nombre:
                raise ConsultaNoPermitida("No se permiten funciones como origen de datos en FROM.")
            if esquema and esquema != "public":
                raise TablaNoAutorizada(f"El esquema '{esquema}' no está disponible para consultas.")
            if not esquema and nombre in nombres_cte:
                continue
            if nombre not in usuario.tablas_autorizadas:
                raise TablaNoAutorizada(
                    f"La tabla '{nombre}' no está habilitada para {usuario.correo}. "
                    "Usa list_tables para ver las tablas permitidas."
                )
            tablas.add(nombre)

        if not tablas:
            raise ConsultaNoPermitida("La consulta debe leer al menos una tabla autorizada.")
        return SqlValidado(sql=texto, tablas=tuple(sorted(tablas)))
