"""Identifica al usuario a partir de su token (encabezado Authorization: Bearer)."""

from __future__ import annotations

from app.aplicacion.puertos import RepositorioUsuarios
from app.dominio.errores import NoAutenticado
from app.dominio.modelos import Usuario


class Autenticador:
    def __init__(self, usuarios: RepositorioUsuarios):
        self._usuarios = usuarios

    def desde_encabezado(self, authorization: str | None) -> Usuario:
        if not authorization or not authorization.lower().startswith("bearer "):
            raise NoAutenticado("Falta el encabezado 'Authorization: Bearer <token>'.")
        token = authorization[7:].strip()
        usuario = self._usuarios.buscar_por_token(token) if token else None
        if usuario is None:
            raise NoAutenticado("Token inválido o usuario inactivo.")
        return usuario
