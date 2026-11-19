"""Adaptador de salida hacia Groq (API compatible con OpenAI).

La llave se lee de la variable de entorno GROQ_API_KEY; nunca se escribe en el código
ni en el repositorio. Si Groq falla o no responde, se devuelve ServicioNoDisponible
para que el usuario pueda pasar al modo de contingencia (consultas predefinidas).
"""

from __future__ import annotations

import time
from typing import Any, Callable

import httpx

from app.dominio.errores import ServicioNoDisponible

URL_GROQ = "https://api.groq.com/openai/v1/chat/completions"
# Plan gratuito de Groq: 8.000 tokens por minuto por modelo. Si se llena, se espera lo que Groq indique
# (si es poco) y luego se prueba un modelo de respaldo, que tiene su propio cupo.
MODELO_RESPALDO = "openai/gpt-oss-20b"
MAX_ESPERA_S = 20.0


class ClienteGroq:
    def __init__(self, api_key: str, modelo: str = "llama-3.3-70b-versatile", timeout_s: float = 30.0,
                 cliente_http: httpx.Client | None = None, modelo_respaldo: str | None = MODELO_RESPALDO,
                 esperar: Callable[[float], None] = time.sleep):
        self.modelo = modelo
        self._api_key = api_key
        self._http = cliente_http or httpx.Client(timeout=timeout_s)
        self._respaldo = modelo_respaldo if modelo_respaldo and modelo_respaldo != modelo else None
        self._esperar = esperar

    def completar(self, mensajes: list[dict[str, Any]], herramientas: list[dict[str, Any]]) -> dict[str, Any]:
        r = self._enviar(self.modelo, mensajes, herramientas)
        if r.status_code == 429:
            espera = _segundos_de_espera(r)
            if espera is not None and espera <= MAX_ESPERA_S:
                self._esperar(espera)
                r = self._enviar(self.modelo, mensajes, herramientas)
        if r.status_code == 429 and self._respaldo:
            r = self._enviar(self._respaldo, mensajes, herramientas)
        if r.status_code == 429:
            raise ServicioNoDisponible("El proveedor de IA alcanzó su límite de uso. Intenta en un minuto "
                                       "o usa el modo de contingencia.")
        if r.status_code >= 400:
            raise ServicioNoDisponible(f"El proveedor de IA respondió con error {r.status_code}: {_detalle(r)}")
        return r.json()["choices"][0]["message"]

    def _enviar(self, modelo: str, mensajes: list[dict[str, Any]], herramientas: list[dict[str, Any]]) -> httpx.Response:
        cuerpo: dict[str, Any] = {"model": modelo, "messages": mensajes, "tools": herramientas,
                                  "tool_choice": "auto", "temperature": 0.1}
        if modelo.startswith("openai/gpt-oss"):
            # Menos razonamiento interno = menos tokens consumidos del cupo por minuto.
            cuerpo["reasoning_effort"] = "low"
        for intento in range(2):
            try:
                r = self._http.post(URL_GROQ, json=cuerpo, headers={"Authorization": f"Bearer {self._api_key}"})
            except httpx.HTTPError as error:
                raise ServicioNoDisponible(f"No se pudo contactar al proveedor de IA: {type(error).__name__}.") from error
            # A veces el modelo arma mal la llamada a una herramienta (tool_use_failed): se reintenta una vez.
            if not (r.status_code == 400 and "tool_use_failed" in r.text and intento == 0):
                break
        return r


def _segundos_de_espera(r: httpx.Response) -> float | None:
    """Groq indica en retry-after cuántos segundos esperar antes de reintentar."""
    try:
        return max(0.0, float(r.headers.get("retry-after", "")))
    except ValueError:
        return None


def _detalle(r: httpx.Response) -> str:
    """Código y mensaje del error de Groq (nunca incluye la llave), para poder diagnosticar."""
    try:
        cuerpo = r.json()
    except ValueError:
        return r.text[:300]
    error = cuerpo.get("error") if isinstance(cuerpo, dict) else None
    if not isinstance(error, dict):
        return ""
    return f"{error.get('code') or error.get('type') or ''} {error.get('message') or ''}".strip()[:300]


class AsistenteNoConfigurado:
    """Se usa cuando no hay GROQ_API_KEY: la API arranca igual y el asistente responde 503."""

    modelo = "sin configurar"

    def completar(self, mensajes: list[dict[str, Any]], herramientas: list[dict[str, Any]]) -> dict[str, Any]:
        raise ServicioNoDisponible("El asistente con IA no está configurado (falta GROQ_API_KEY). "
                                   "Usa el modo de contingencia: /api/contingencia/consultas.")
