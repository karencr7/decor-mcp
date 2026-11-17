"""Configuración leída SOLO de variables de entorno (nunca de archivos versionados).

Ver .env.example para la lista de variables, sin valores reales.
"""

from functools import lru_cache

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Configuracion(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="DECOR_", env_file=None, extra="ignore")

    # Conexión de solo lectura para las consultas de negocio (rol decor_lector).
    db_lector_url: str
    # Conexión para usuarios, permisos y auditoría (rol decor_app).
    db_app_url: str
    # Hosts aceptados por el endpoint MCP (protección contra DNS rebinding).
    mcp_hosts_permitidos: str = "localhost:*,127.0.0.1:*,[::1]:*"
    # Segundos que se guarda en memoria el catálogo de tablas.
    catalogo_ttl_s: int = 60
    # Asistente con IA (Groq). La llave llega por la variable GROQ_API_KEY y nunca se versiona.
    groq_api_key: str | None = Field(default=None, validation_alias=AliasChoices("GROQ_API_KEY", "DECOR_GROQ_API_KEY"))
    groq_modelo: str = "llama-3.3-70b-versatile"


@lru_cache
def obtener_configuracion() -> Configuracion:
    return Configuracion()  # type: ignore[call-arg]
