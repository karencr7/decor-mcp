"""Entidades y objetos de valor del dominio.

Este paquete NO importa nada de bases de datos, HTTP ni MCP: es el centro
del hexágono (Figura 2 de la propuesta) y se puede probar de forma aislada.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


@dataclass(frozen=True)
class Usuario:
    """Colaborador autenticado y las tablas que tiene habilitadas (mcp_permisos)."""

    correo: str
    nombre: str
    area: str
    es_admin: bool
    tablas_autorizadas: frozenset[str]


class TipoConsulta(str, Enum):
    """Las dos herramientas de SQL libre del diseño, con límites distintos."""

    DETALLE = "query_table"        # hasta 2.000 filas
    ANALITICA = "query_analytics"  # hasta 500 filas y 15 s


class Canal(str, Enum):
    """Por dónde llegó la solicitud. Se guarda en la auditoría."""

    MCP = "MCP"
    REST = "REST"
    CONTINGENCIA = "CONTINGENCIA"
    ASISTENTE = "ASISTENTE_IA"  # asistente con IA integrado (Groq), Módulo 6


@dataclass(frozen=True)
class Columna:
    nombre: str
    tipo: str
    descripcion: str | None = None


@dataclass(frozen=True)
class Tabla:
    nombre: str
    descripcion: str | None
    columnas: tuple[Columna, ...]

    def tiene_columna(self, nombre: str) -> bool:
        return any(c.nombre == nombre for c in self.columnas)


@dataclass
class ResultadoConsulta:
    columnas: list[str]
    filas: list[dict[str, Any]]
    truncado: bool = False
    limite_aplicado: int | None = None

    @property
    def total_filas(self) -> int:
        return len(self.filas)

    def como_dict(self) -> dict[str, Any]:
        return {
            "columnas": self.columnas,
            "filas": self.filas,
            "total_filas": self.total_filas,
            "truncado": self.truncado,
            "limite_aplicado": self.limite_aplicado,
        }


@dataclass
class EntradaAuditoria:
    """Quién consultó qué, cuándo, por qué canal y con qué resultado."""

    correo: str | None
    canal: Canal
    herramienta: str
    resultado: str               # OK | DENEGADA | ERROR
    detalle: str | None = None   # SQL o argumentos (recortado)
    tablas: list[str] = field(default_factory=list)
    motivo: str | None = None
    filas: int | None = None
    duracion_ms: int | None = None
