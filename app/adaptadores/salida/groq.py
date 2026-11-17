"""Adaptador de salida hacia Groq (API compatible con OpenAI).

La llave se lee de la variable de entorno GROQ_API_KEY; nunca se escribe en el código
ni en el repositorio. Si Groq falla o no responde, se devuelve ServicioNoDisponible
para que el usuario pueda pasar al modo de contingencia (consultas predefinidas).
"""

from __future__ import annotations

from typing import Any

import httpx

from app.dominio.errores import ServicioNoDisponible

URL_GROQ = "https://api.groq.com/openai/v1/chat/completions"


class ClienteGroq:
    def __init__(self, api_key: str, modelo: str = "llama-3.3-70b-versatile", timeout_s: float = 30.0,
                 cliente_http: httpx.Client | None = None):
        self.modelo = modelo
        self._api_key = api_key
        self._http = cliente_http or httpx.Client(timeout=timeout_s)

    def completar(self, mensajes: list[dict[str, Any]], herramientas: list[dict[str, Any]]) -> dict[str, Any]:
        cuerpo = {"model": self.modelo, "messages": mensajes, "tools": herramientas,
                  "tool_choice": "auto", "temperature": 0.1}
        try:
            r = self._http.post(URL_GROQ, json=cuerpo, headers={"Authorization": f"Bearer {self._api_key}"})
        except httpx.HTTPError as error:
            raise ServicioNoDisponible(f"No se pudo contactar al proveedor de IA: {type(error).__name__}.") from error
        if r.status_code == 429:
            raise ServicioNoDisponible("El proveedor de IA alcanzó su límite de uso. Intenta en un minuto "
                                       "o usa el modo de contingencia.")
        if r.status_code >= 400:
            raise ServicioNoDisponible(f"El proveedor de IA respondió con error {r.status_code}.")
        return r.json()["choices"][0]["message"]


class AsistenteNoConfigurado:
    """Se usa cuando no hay GROQ_API_KEY: la API arranca igual y el asistente responde 503."""

    modelo = "sin configurar"

    def completar(self, mensajes: list[dict[str, Any]], herramientas: list[dict[str, Any]]) -> dict[str, Any]:
        raise ServicioNoDisponible("El asistente con IA no está configurado (falta GROQ_API_KEY). "
                                   "Usa el modo de contingencia: /api/contingencia/consultas.")
