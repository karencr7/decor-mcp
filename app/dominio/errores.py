"""Errores del dominio. Cada adaptador de entrada los traduce a su protocolo:
REST -> código HTTP; MCP -> resultado con isError=true y el motivo."""


class ErrorDecor(Exception):
    """Error base con un mensaje pensado para el usuario (o para que la IA corrija)."""

    codigo = "ERROR"

    def __init__(self, mensaje: str):
        super().__init__(mensaje)
        self.mensaje = mensaje


class NoAutenticado(ErrorDecor):
    codigo = "NO_AUTENTICADO"


class ConsultaNoPermitida(ErrorDecor):
    """La sentencia no es un SELECT/WITH único y de solo lectura."""

    codigo = "CONSULTA_NO_PERMITIDA"


class TablaNoAutorizada(ErrorDecor):
    """La tabla no está habilitada para este usuario en mcp_permisos."""

    codigo = "TABLA_NO_AUTORIZADA"


class ParametroInvalido(ErrorDecor):
    codigo = "PARAMETRO_INVALIDO"


class RecursoNoEncontrado(ErrorDecor):
    codigo = "NO_ENCONTRADO"


class TiempoAgotado(ErrorDecor):
    codigo = "TIEMPO_AGOTADO"


class ServicioNoDisponible(ErrorDecor):
    """La base de datos no responde."""

    codigo = "SERVICIO_NO_DISPONIBLE"


class ErrorEjecucion(ErrorDecor):
    """La base rechazó la consulta (columna inexistente, tipos, etc.)."""

    codigo = "ERROR_EJECUCION"
