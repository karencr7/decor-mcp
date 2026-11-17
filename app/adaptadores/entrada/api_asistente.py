"""Adaptador de entrada del asistente con IA: endpoint REST y una página web mínima.

POST /api/asistente/preguntar  -> pregunta en español, respuesta del LLM + herramientas usadas
GET  /asistente                -> página para la demo (pide token y pregunta)
"""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, FastAPI
from fastapi.responses import HTMLResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

from app.aplicacion.asistente import MAX_LARGO_PREGUNTA, Asistente
from app.aplicacion.autenticacion import Autenticador
from app.dominio.modelos import Usuario


class SolicitudPregunta(BaseModel):
    pregunta: str = Field(..., min_length=1, max_length=MAX_LARGO_PREGUNTA,
                          examples=["¿Cuántas facturas emitió cada oficina en septiembre de 2026?"])


def registrar_asistente(app: FastAPI, asistente: Asistente, autenticador: Autenticador) -> None:
    bearer = HTTPBearer(auto_error=False, description="Token del usuario (ver .env)")

    def usuario_actual(credenciales: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]) -> Usuario:
        encabezado = f"Bearer {credenciales.credentials}" if credenciales else None
        return autenticador.desde_encabezado(encabezado)

    router = APIRouter(tags=["Asistente con IA (Groq)"])

    @router.post("/api/asistente/preguntar", summary="Pregunta en lenguaje natural respondida por IA",
                 responses={401: {"description": "Falta el token o es inválido"},
                            400: {"description": "Pregunta vacía o muy larga"},
                            503: {"description": "Proveedor de IA no disponible o sin configurar"}})
    def preguntar(usuario: Annotated[Usuario, Depends(usuario_actual)], solicitud: SolicitudPregunta) -> dict[str, Any]:
        return asistente.preguntar(usuario, solicitud.pregunta)

    @router.get("/asistente", include_in_schema=False)
    def pagina() -> HTMLResponse:
        return HTMLResponse(PAGINA_HTML)

    app.include_router(router)


PAGINA_HTML = """<!doctype html>
<html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Asistente Decor MCP</title>
<style>
 body{font-family:system-ui,sans-serif;max-width:760px;margin:2rem auto;padding:0 1rem;color:#1f2937;background:#f8fafc}
 h1{font-size:1.4rem} label{display:block;margin:.8rem 0 .3rem;font-weight:600}
 input,textarea{width:100%;padding:.6rem;border:1px solid #cbd5e1;border-radius:8px;font:inherit;box-sizing:border-box}
 button{margin-top:.8rem;padding:.6rem 1.2rem;border:0;border-radius:8px;background:#1d4ed8;color:#fff;font-weight:600;cursor:pointer}
 button:disabled{opacity:.6} .caja{background:#fff;border:1px solid #e2e8f0;border-radius:8px;padding:1rem;margin-top:1rem;white-space:pre-wrap}
 .chip{display:inline-block;padding:.1rem .5rem;margin:.1rem;border-radius:999px;font-size:.8rem;background:#e0e7ff}
 .chip.error{background:#fee2e2} small{color:#64748b}
</style></head><body>
<h1>Asistente de datos · Decor MCP</h1>
<small>MVP con datos ficticios. La IA (Groq) solo puede usar las 8 herramientas de solo lectura,
con los permisos de tu token. Cada consulta queda en la auditoría.</small>
<label for="token">Token</label><input id="token" type="password" autocomplete="off" placeholder="DECOR_TOKEN_COMERCIAL">
<label for="pregunta">Pregunta</label>
<textarea id="pregunta" rows="3">¿Cuántas facturas emitió cada oficina en septiembre de 2026?</textarea>
<button id="enviar">Preguntar</button>
<div id="salida"></div>
<script>
const $ = (id) => document.getElementById(id);
$("enviar").onclick = async () => {
  $("enviar").disabled = true; $("salida").innerHTML = '<div class="caja">Pensando…</div>';
  try {
    const r = await fetch("/api/asistente/preguntar", {method: "POST",
      headers: {"Content-Type": "application/json", "Authorization": "Bearer " + $("token").value},
      body: JSON.stringify({pregunta: $("pregunta").value})});
    const d = await r.json();
    const caja = document.createElement("div"); caja.className = "caja";
    if (!r.ok) { caja.textContent = "Error " + r.status + ": " + (d.mensaje || JSON.stringify(d)); }
    else {
      caja.textContent = d.respuesta;
      const h = document.createElement("div"); h.style.marginTop = ".8rem";
      h.innerHTML = "<small>Herramientas usadas (" + d.modelo + "):</small> ";
      d.herramientas_usadas.forEach(u => { const s = document.createElement("span");
        s.className = "chip" + (u.ok ? "" : " error"); s.textContent = u.herramienta; h.appendChild(s); });
      caja.appendChild(h);
    }
    $("salida").replaceChildren(caja);
  } catch (e) { $("salida").innerHTML = '<div class="caja">No se pudo conectar con la API.</div>'; }
  $("enviar").disabled = false;
};
</script></body></html>"""
