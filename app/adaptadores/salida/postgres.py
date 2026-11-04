"""Adaptadores de salida para PostgreSQL (equivalen al «Adaptador Supabase» y al
«Adaptador de registros» de la Figura 2).

Cambiar de base de datos solo exige reemplazar este archivo: el núcleo
(dominio y aplicación) no importa psycopg.
"""

from __future__ import annotations

import hashlib
import threading
import time
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Sequence
from uuid import UUID

import psycopg
from psycopg import errors as pg_errors
from psycopg.rows import dict_row

from app.aplicacion.puertos import RegistroAuditoria, RepositorioDatos, RepositorioUsuarios
from app.dominio.errores import (
    ConsultaNoPermitida, ErrorEjecucion, ServicioNoDisponible, TablaNoAutorizada, TiempoAgotado,
)
from app.dominio.modelos import Columna, EntradaAuditoria, ResultadoConsulta, Tabla, Usuario

_SQL_CATALOGO = """
SELECT c.relname                                   AS tabla,
       obj_description(c.oid, 'pg_class')          AS descripcion_tabla,
       a.attname                                   AS columna,
       format_type(a.atttypid, a.atttypmod)        AS tipo,
       col_description(c.oid, a.attnum)            AS descripcion_columna
  FROM pg_class c
  JOIN pg_namespace n ON n.oid = c.relnamespace
  JOIN pg_attribute a ON a.attrelid = c.oid
 WHERE n.nspname = 'public' AND c.relkind IN ('r', 'v', 'm')
   AND a.attnum > 0 AND NOT a.attisdropped
 ORDER BY c.relname, a.attnum
"""


def _a_json(valor: Any) -> Any:
    """Convierte tipos de PostgreSQL a valores que se pueden enviar en JSON."""
    if isinstance(valor, Decimal):
        return float(valor)
    if isinstance(valor, (datetime, date)):
        return valor.isoformat()
    if isinstance(valor, UUID):
        return str(valor)
    return valor


def _conectar(dsn: str, **kwargs) -> psycopg.Connection:
    try:
        return psycopg.connect(dsn, connect_timeout=5, **kwargs)
    except psycopg.OperationalError as error:
        raise ServicioNoDisponible("La base de datos no está disponible en este momento.") from error


class RepositorioDatosPostgres(RepositorioDatos):
    """Ejecuta consultas con el rol decor_lector, en transacción de SOLO LECTURA,
    con tiempo máximo (statement_timeout) y límite de filas."""

    def __init__(self, dsn: str, catalogo_ttl_s: int = 60):
        self._dsn = dsn
        self._ttl = catalogo_ttl_s
        self._catalogo: dict[str, Tabla] | None = None
        self._catalogo_en = 0.0
        self._candado = threading.Lock()

    def catalogo(self) -> dict[str, Tabla]:
        with self._candado:
            if self._catalogo is None or time.monotonic() - self._catalogo_en > self._ttl:
                self._catalogo = self._leer_catalogo()
                self._catalogo_en = time.monotonic()
            return self._catalogo

    def _leer_catalogo(self) -> dict[str, Tabla]:
        with _conectar(self._dsn, row_factory=dict_row) as conn:
            filas = conn.execute(_SQL_CATALOGO).fetchall()
        agrupado: dict[str, tuple[str | None, list[Columna]]] = {}
        for f in filas:
            descripcion, columnas = agrupado.setdefault(f["tabla"], (f["descripcion_tabla"], []))
            columnas.append(Columna(f["columna"], f["tipo"], f["descripcion_columna"]))
        return {nombre: Tabla(nombre, desc, tuple(cols)) for nombre, (desc, cols) in agrupado.items()}

    def ejecutar(self, sql: str, parametros: Sequence[Any] | dict[str, Any] | None,
                 max_filas: int, tiempo_maximo_s: int) -> ResultadoConsulta:
        # Se envuelve la consulta para que la BASE corte en max_filas + 1
        # (la fila extra solo sirve para saber si el resultado quedó truncado).
        envuelta = f"SELECT * FROM (\n{sql}\n) AS consulta_decor LIMIT {int(max_filas) + 1}"
        try:
            with _conectar(self._dsn) as conn:
                with conn.cursor() as cur:
                    cur.execute("SET TRANSACTION READ ONLY")
                    cur.execute("SELECT set_config('statement_timeout', %s, true)", (f"{int(tiempo_maximo_s * 1000)}",))
                    cur.execute(envuelta, parametros)
                    columnas = self._nombres_unicos([d.name for d in cur.description or []])
                    filas = cur.fetchall()
                conn.rollback()
        except pg_errors.QueryCanceled as error:
            raise TiempoAgotado(f"La consulta superó el tiempo máximo de {tiempo_maximo_s} s. "
                                "Agrega filtros de fecha u oficina.") from error
        except pg_errors.InsufficientPrivilege as error:
            raise TablaNoAutorizada("La base de datos rechazó el acceso a un objeto no permitido.") from error
        except pg_errors.ReadOnlySqlTransaction as error:
            raise ConsultaNoPermitida("Solo se permiten operaciones de lectura.") from error
        except psycopg.Error as error:
            mensaje = getattr(getattr(error, "diag", None), "message_primary", None) or str(error)
            raise ErrorEjecucion(f"La base de datos rechazó la consulta: {mensaje}") from error

        truncado = len(filas) > max_filas
        filas = filas[:max_filas]
        return ResultadoConsulta(
            columnas=columnas,
            filas=[{c: _a_json(v) for c, v in zip(columnas, fila)} for fila in filas],
            truncado=truncado,
            limite_aplicado=max_filas,
        )

    def ultima_carga(self) -> datetime | None:
        try:
            with _conectar(self._dsn) as conn:
                fila = conn.execute("SELECT max(ultima_carga) FROM public.dv_meta").fetchone()
        except psycopg.Error:
            return None
        return fila[0] if fila else None

    @staticmethod
    def _nombres_unicos(nombres: list[str]) -> list[str]:
        vistos: dict[str, int] = {}
        unicos = []
        for n in nombres:
            vistos[n] = vistos.get(n, 0) + 1
            unicos.append(n if vistos[n] == 1 else f"{n}_{vistos[n]}")
        return unicos


class RepositorioUsuariosPostgres(RepositorioUsuarios):
    """Lee mcp.usuarios y mcp.permisos con el rol decor_app."""

    def __init__(self, dsn: str):
        self._dsn = dsn

    def buscar_por_token(self, token: str) -> Usuario | None:
        token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
        with _conectar(self._dsn, row_factory=dict_row) as conn:
            fila = conn.execute(
                """SELECT u.correo, u.nombre, u.area, u.es_admin,
                          coalesce(array_agg(p.tabla) FILTER (WHERE p.tabla IS NOT NULL), '{}') AS tablas
                     FROM mcp.usuarios u
                     LEFT JOIN mcp.permisos p ON p.correo = u.correo
                    WHERE u.token_hash = %s AND u.activo
                    GROUP BY u.correo""",
                (token_hash,),
            ).fetchone()
        if fila is None:
            return None
        return Usuario(fila["correo"], fila["nombre"], fila["area"], fila["es_admin"],
                       frozenset(t.lower() for t in fila["tablas"]))


class RegistroAuditoriaPostgres(RegistroAuditoria):
    """Escribe en mcp.auditoria con el rol decor_app."""

    def __init__(self, dsn: str):
        self._dsn = dsn

    def registrar(self, entrada: EntradaAuditoria) -> None:
        with _conectar(self._dsn) as conn:
            conn.execute(
                """INSERT INTO mcp.auditoria
                       (correo, canal, herramienta, detalle, tablas, resultado, motivo, filas, duracion_ms)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (entrada.correo, entrada.canal.value, entrada.herramienta, entrada.detalle,
                 ",".join(entrada.tablas) or None, entrada.resultado, entrada.motivo,
                 entrada.filas, entrada.duracion_ms),
            )

    def ultimas(self, limite: int) -> list[dict[str, Any]]:
        with _conectar(self._dsn, row_factory=dict_row) as conn:
            filas = conn.execute(
                """SELECT id, fecha, correo, canal, herramienta, detalle, tablas,
                          resultado, motivo, filas, duracion_ms
                     FROM mcp.auditoria ORDER BY id DESC LIMIT %s""",
                (limite,),
            ).fetchall()
        return [{k: _a_json(v) for k, v in f.items()} for f in filas]
