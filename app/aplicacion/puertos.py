"""Puertos de salida (interfaces) que usa el núcleo sin conocer la tecnología.

Cada puerto tiene un adaptador PostgreSQL en app/adaptadores/salida y un
adaptador simulado en tests/ (así se prueba el núcleo sin base de datos).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Sequence

from app.dominio.modelos import EntradaAuditoria, ResultadoConsulta, Tabla, Usuario


class RepositorioDatos(ABC):
    """Puerto «Repositorio de datos»: lectura de las tablas de negocio."""

    @abstractmethod
    def catalogo(self) -> dict[str, Tabla]:
        """Tablas de negocio con sus columnas y descripciones (COMMENT)."""

    @abstractmethod
    def ejecutar(
        self,
        sql: str,
        parametros: Sequence[Any] | dict[str, Any] | None,
        max_filas: int,
        tiempo_maximo_s: int,
    ) -> ResultadoConsulta:
        """Ejecuta una consulta de SOLO LECTURA y devuelve como máximo max_filas."""

    @abstractmethod
    def ultima_carga(self) -> datetime | None:
        """Fecha de la última carga de datos desde SAP (dv_meta)."""


class RepositorioUsuarios(ABC):
    """Usuarios y tablas habilitadas (mcp_permisos)."""

    @abstractmethod
    def buscar_por_token(self, token: str) -> Usuario | None: ...


class RegistroAuditoria(ABC):
    """Puerto «Registro de auditoría»."""

    @abstractmethod
    def registrar(self, entrada: EntradaAuditoria) -> None: ...

    @abstractmethod
    def ultimas(self, limite: int) -> list[dict[str, Any]]: ...
