"""Inicio de sesión del asistente web: usuario (correo) + token. Sin base de datos."""

import pytest
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from app.adaptadores.entrada.api_asistente import registrar_asistente
from app.adaptadores.salida.groq import AsistenteNoConfigurado
from app.aplicacion.asistente import Asistente
from app.aplicacion.autenticacion import Autenticador
from app.dominio.errores import ErrorDecor
from app.dominio.modelos import Usuario

COMERCIAL = Usuario("comercial@decor-demo.co", "Funcionario Comercial (demo)", "Comercial", False,
                    frozenset({"zventas", "mv_zpedidos"}))


class UsuariosFalsos:
    def buscar_por_token(self, token):
        return COMERCIAL if token == "token-comercial" else None


@pytest.fixture
def cliente():
    app = FastAPI()

    @app.exception_handler(ErrorDecor)
    async def manejar(_, error):
        return JSONResponse(status_code=401 if error.codigo == "NO_AUTENTICADO" else 503,
                            content={"error": error.codigo, "mensaje": error.mensaje})

    autenticador = Autenticador(UsuariosFalsos())
    registrar_asistente(app, Asistente(None, AsistenteNoConfigurado()), autenticador)
    return TestClient(app)


def test_sesion_valida_devuelve_el_perfil_sin_el_token(cliente):
    r = cliente.post("/api/sesion", json={"correo": " Comercial@Decor-Demo.co ", "token": "token-comercial"})
    assert r.status_code == 200
    assert r.json() == {"correo": "comercial@decor-demo.co", "nombre": "Funcionario Comercial (demo)",
                        "area": "Comercial", "es_admin": False, "tablas": ["mv_zpedidos", "zventas"]}
    assert "token" not in r.text


@pytest.mark.parametrize("correo, token", [
    ("comercial@decor-demo.co", "token-equivocado"),   # token mal
    ("admin@decor-demo.co", "token-comercial"),        # token de otro usuario
    ("comercial@decor-demo.co", " "),                  # token vacío
])
def test_sesion_invalida_responde_401_con_mensaje_generico(cliente, correo, token):
    r = cliente.post("/api/sesion", json={"correo": correo, "token": token})
    assert r.status_code == 401
    assert r.json()["mensaje"] == "Usuario o token incorrectos."


def test_pagina_tiene_inicio_de_sesion_con_usuario_y_token(cliente):
    html = cliente.get("/asistente").text
    assert 'id="correo"' in html and 'id="token"' in html and "/api/sesion" in html
