"""Adaptador de entrada del asistente con IA: inicio de sesión, endpoint REST y página web.

POST /api/sesion               -> valida usuario (correo) + token y devuelve el perfil
POST /api/asistente/preguntar  -> pregunta en español, respuesta del LLM + herramientas usadas
GET  /asistente                -> aplicación web: inicio de sesión y chat con el asistente
"""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, FastAPI
from fastapi.responses import HTMLResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

from app.aplicacion.asistente import MAX_LARGO_PREGUNTA, Asistente
from app.aplicacion.autenticacion import Autenticador
from app.dominio.errores import NoAutenticado
from app.dominio.modelos import Usuario


class SolicitudPregunta(BaseModel):
    pregunta: str = Field(..., min_length=1, max_length=MAX_LARGO_PREGUNTA,
                          examples=["¿Cuántas facturas emitió cada oficina en septiembre de 2026?"])


class SolicitudSesion(BaseModel):
    correo: str = Field(..., min_length=3, max_length=200, examples=["comercial@decor-demo.co"])
    token: str = Field(..., min_length=1, max_length=500)


def perfil(usuario: Usuario) -> dict[str, Any]:
    return {"correo": usuario.correo, "nombre": usuario.nombre, "area": usuario.area,
            "es_admin": usuario.es_admin, "tablas": sorted(usuario.tablas_autorizadas)}


def registrar_asistente(app: FastAPI, asistente: Asistente, autenticador: Autenticador) -> None:
    bearer = HTTPBearer(auto_error=False, description="Token del usuario (ver .env)")

    def usuario_actual(credenciales: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]) -> Usuario:
        encabezado = f"Bearer {credenciales.credentials}" if credenciales else None
        return autenticador.desde_encabezado(encabezado)

    router = APIRouter(tags=["Asistente con IA (Groq)"])

    @router.post("/api/sesion", summary="Inicio de sesión: usuario (correo) + token",
                 responses={401: {"description": "Usuario o token incorrectos"}})
    def iniciar_sesion(solicitud: SolicitudSesion) -> dict[str, Any]:
        try:
            usuario = autenticador.desde_encabezado(f"Bearer {solicitud.token.strip()}")
        except NoAutenticado:
            usuario = None
        # Mismo mensaje si falla el correo o el token: no se revela cuál de los dos está mal.
        if usuario is None or usuario.correo.lower() != solicitud.correo.strip().lower():
            raise NoAutenticado("Usuario o token incorrectos.")
        return perfil(usuario)

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


PAGINA_HTML = r"""<!doctype html>
<html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Decor MCP · Asistente de datos</title>
<style>
:root{--ink:#1B2430;--paper:#F7F5F0;--card:#FFFFFF;--accent:#B5472F;--gold:#E3A84E;--muted:#5B6575;--line:#E4DED3;--ok:#2F7D5B;--bad:#B42318}
*{box-sizing:border-box}
body{margin:0;font-family:system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;color:var(--ink);background:var(--paper)}
.oculto{display:none!important}
/* ---------- inicio de sesión ---------- */
#login{min-height:100vh;display:grid;grid-template-columns:1.1fr 1fr}
.marca{background:linear-gradient(150deg,#1B2430 0%,#2B3A50 60%,#B5472F 140%);color:#F7F5F0;padding:56px;display:flex;flex-direction:column;justify-content:space-between}
.logo{display:flex;align-items:center;gap:12px;font-weight:700;font-size:20px;letter-spacing:.5px}
.logo span{width:40px;height:40px;border-radius:10px;background:var(--gold);color:var(--ink);display:grid;place-items:center;font-size:20px}
.marca h1{font-size:44px;line-height:1.1;margin:0 0 16px}
.marca p{color:#C9D3DE;font-size:17px;line-height:1.5;max-width:460px}
.puntos{display:grid;gap:12px;margin-top:28px}
.puntos div{display:flex;gap:10px;align-items:flex-start;color:#DCE3EA;font-size:15px}
.puntos b{color:var(--gold)}
.formulario{display:grid;place-items:center;padding:32px}
.caja{width:100%;max-width:400px;background:var(--card);border:1px solid var(--line);border-radius:18px;padding:36px;box-shadow:0 10px 30px rgba(27,36,48,.08)}
.caja h2{margin:0 0 6px;font-size:26px}
.caja .sub{margin:0 0 24px;color:var(--muted);font-size:14px}
label{display:block;font-weight:600;font-size:14px;margin:16px 0 6px}
input,textarea{width:100%;padding:12px 14px;border:1px solid #CFC8BB;border-radius:10px;font:inherit;background:#FFFDF9}
input:focus,textarea:focus{outline:2px solid var(--gold);border-color:transparent}
.clave{position:relative}.clave button{position:absolute;right:8px;top:7px;border:0;background:none;color:var(--muted);cursor:pointer;font-size:13px;padding:6px}
.btn{width:100%;margin-top:22px;padding:13px;border:0;border-radius:10px;background:var(--accent);color:#fff;font-weight:700;font-size:15px;cursor:pointer}
.btn:disabled{opacity:.6;cursor:wait}
.error{margin-top:14px;color:var(--bad);font-size:14px;min-height:20px}
.demo{margin-top:18px;font-size:12.5px;color:var(--muted);border-top:1px solid var(--line);padding-top:14px;line-height:1.6}
/* ---------- aplicación ---------- */
#app{min-height:100vh;display:grid;grid-template-rows:auto 1fr}
header{background:var(--ink);color:#F7F5F0;padding:14px 28px;display:flex;align-items:center;justify-content:space-between;gap:16px}
.usuario{display:flex;align-items:center;gap:12px}
.avatar{width:38px;height:38px;border-radius:50%;background:var(--gold);color:var(--ink);display:grid;place-items:center;font-weight:700}
.usuario small{display:block;color:#C9D3DE}
.rol{font-size:12px;padding:3px 10px;border-radius:999px;background:#33435A;color:#F7F5F0;margin-left:8px}
.salir{background:transparent;color:#F7F5F0;border:1px solid #4A5B73;border-radius:8px;padding:8px 14px;cursor:pointer}
main{display:grid;grid-template-columns:300px 1fr;gap:24px;padding:24px 28px;max-width:1280px;width:100%;margin:0 auto}
aside{display:flex;flex-direction:column;gap:16px}
.panel{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:18px}
.panel h3{margin:0 0 10px;font-size:13px;text-transform:uppercase;letter-spacing:1px;color:var(--accent)}
.sugerencia{display:block;width:100%;text-align:left;background:#FBF7F0;border:1px solid var(--line);border-radius:10px;padding:10px 12px;margin-bottom:8px;cursor:pointer;font:inherit;font-size:14px;color:var(--ink)}
.sugerencia:hover{border-color:var(--gold)}
.tablas{display:flex;flex-wrap:wrap;gap:6px}
.tablas span{font-size:12px;background:#EEF2F6;border-radius:6px;padding:3px 8px;font-family:ui-monospace,monospace}
.seguro{font-size:13px;color:var(--muted);line-height:1.5}
.chat{background:var(--card);border:1px solid var(--line);border-radius:14px;display:grid;grid-template-rows:1fr auto;min-height:70vh;overflow:hidden}
.mensajes{padding:22px;overflow-y:auto;display:flex;flex-direction:column;gap:16px;max-height:calc(100vh - 230px)}
.burbuja{max-width:86%;padding:14px 16px;border-radius:14px;line-height:1.55;font-size:15px}
.yo{align-self:flex-end;background:var(--ink);color:#F7F5F0;border-bottom-right-radius:4px}
.ia{align-self:flex-start;background:#F5F1EA;border-bottom-left-radius:4px}
.ia table{border-collapse:collapse;margin:10px 0;font-size:14px;background:#fff}
.ia th,.ia td{border:1px solid var(--line);padding:6px 10px;text-align:left}.ia th{background:#EFE8DC}
.ia code{background:#E9E2D6;padding:1px 5px;border-radius:4px;font-size:13px}
.meta{margin-top:10px;font-size:12px;color:var(--muted);display:flex;flex-wrap:wrap;gap:6px;align-items:center}
.chip{padding:2px 9px;border-radius:999px;background:#E3E9F4;color:#24426B;font-weight:600}
.chip.mal{background:#FBE3E1;color:var(--bad)}
.escribiendo{color:var(--muted);font-style:italic}
.entrada{display:flex;gap:10px;padding:14px;border-top:1px solid var(--line);background:#FCFAF6}
.entrada textarea{resize:none;height:52px}
.entrada button{width:auto;margin:0;padding:0 22px}
.bienvenida{color:var(--muted);text-align:center;margin:auto;max-width:440px;line-height:1.6}
.bienvenida b{color:var(--ink)}
@media (max-width:900px){#login{grid-template-columns:1fr}.marca{padding:32px}.marca h1{font-size:32px}main{grid-template-columns:1fr;padding:16px}.mensajes{max-height:none}}
</style></head><body>

<section id="login">
  <div class="marca">
    <div class="logo"><span>D</span>Decor MCP</div>
    <div>
      <h1>Pregunta por tus datos en español.</h1>
      <p>El asistente consulta las ventas, pedidos, cartera y existencias de Grupo Decor y responde con cifras reales de la base, solo con los permisos de tu usuario.</p>
      <div class="puntos">
        <div><b>01</b> Solo lectura: la IA no puede modificar ni borrar datos.</div>
        <div><b>02</b> Cada usuario ve únicamente sus tablas autorizadas.</div>
        <div><b>03</b> Toda consulta queda registrada en la auditoría.</div>
      </div>
    </div>
    <small style="color:#9FB0C3">MVP con datos ficticios · Ley 1581 de 2012</small>
  </div>
  <div class="formulario">
    <form class="caja" id="formLogin" autocomplete="off">
      <h2>Iniciar sesión</h2>
      <p class="sub">Ingresa tu usuario y el token que te entregó TI.</p>
      <label for="correo">Usuario (correo)</label>
      <input id="correo" type="email" placeholder="comercial@decor-demo.co" required>
      <label for="token">Token</label>
      <div class="clave"><input id="token" type="password" placeholder="••••••••••" required><button type="button" id="ver">Mostrar</button></div>
      <button class="btn" id="entrar" type="submit">Ingresar</button>
      <div class="error" id="errorLogin" role="alert"></div>
      <div class="demo">Usuarios de demostración: <b>comercial@decor-demo.co</b>, <b>cartera@decor-demo.co</b>, <b>admin@decor-demo.co</b>. El token de cada uno está en las variables <code>DECOR_TOKEN_*</code>.</div>
    </form>
  </div>
</section>

<section id="app" class="oculto">
  <header>
    <div class="usuario"><div class="avatar" id="avatar"></div><div><b id="nombre"></b><span class="rol" id="rol"></span><small id="area"></small></div></div>
    <button class="salir" id="salir">Cerrar sesión</button>
  </header>
  <main>
    <aside>
      <div class="panel"><h3>Prueba con</h3><div id="sugerencias"></div></div>
      <div class="panel"><h3>Tus tablas</h3><div class="tablas" id="tablas"></div></div>
      <div class="panel seguro">La IA (Groq) solo usa 8 herramientas de solo lectura. Si pides algo fuera de tus permisos, el servidor lo bloquea y la IA te lo explica.</div>
    </aside>
    <div class="chat">
      <div class="mensajes" id="mensajes"><div class="bienvenida" id="bienvenida"></div></div>
      <form class="entrada" id="formPregunta">
        <textarea id="pregunta" maxlength="500" placeholder="Escribe tu pregunta… (Enter para enviar)"></textarea>
        <button class="btn" id="enviar" type="submit">Enviar</button>
      </form>
    </div>
  </main>
</section>

<script>
const $ = (id) => document.getElementById(id);
let sesion = null; // {token, perfil} solo en memoria: se borra al cerrar la pestaña

const SUGERENCIAS = {
  "Comercial": ["¿Cuántas facturas emitió cada oficina en septiembre de 2026?", "¿Cuántos pedidos están abiertos y cuánto suman?", "¿Cuál es el material con más existencias en Decorcerámica?", "Muéstrame el correo de los clientes"],
  "Cartera": ["¿Qué clientes tienen más cartera vencida?", "¿Cuánto suma la cartera vencida a octubre de 2026?", "¿Cuántas facturas se emitieron en septiembre de 2026?"],
  "_": ["¿Qué tablas puedo consultar y qué contienen?", "¿Cuántas facturas emitió cada oficina en septiembre de 2026?", "¿Cuántas PQR abiertas hay por oficina?"]
};

const esc = (t) => t.replace(/[&<>"']/g, (c) => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
function enLinea(t){ return esc(t).replace(/\*\*(.+?)\*\*/g,"<b>$1</b>").replace(/`([^`]+)`/g,"<code>$1</code>"); }
function formatear(texto){
  const lineas = texto.split("\n"); let html = ""; let i = 0;
  while (i < lineas.length){
    if (/^\s*\|.*\|\s*$/.test(lineas[i])){
      const filas = [];
      while (i < lineas.length && /^\s*\|.*\|\s*$/.test(lineas[i])){ filas.push(lineas[i]); i++; }
      const celdas = (f) => f.trim().replace(/^\||\|$/g,"").split("|").map(c => c.trim());
      const datos = filas.filter(f => !/^\s*\|[\s:\-|]+\|\s*$/.test(f)).map(celdas);
      if (datos.length){
        html += "<table><tr>" + datos[0].map(c => "<th>"+enLinea(c)+"</th>").join("") + "</tr>";
        datos.slice(1).forEach(r => html += "<tr>" + r.map(c => "<td>"+enLinea(c)+"</td>").join("") + "</tr>");
        html += "</table>";
      }
      continue;
    }
    html += lineas[i].trim() ? "<div>"+enLinea(lineas[i])+"</div>" : "<div style='height:8px'></div>";
    i++;
  }
  return html;
}

function burbuja(clase, html){
  $("bienvenida")?.remove();
  const d = document.createElement("div"); d.className = "burbuja " + clase; d.innerHTML = html;
  $("mensajes").appendChild(d); $("mensajes").scrollTop = $("mensajes").scrollHeight; return d;
}

$("ver").onclick = () => { const t = $("token"); t.type = t.type === "password" ? "text" : "password"; $("ver").textContent = t.type === "password" ? "Mostrar" : "Ocultar"; };

$("formLogin").onsubmit = async (e) => {
  e.preventDefault(); $("errorLogin").textContent = ""; $("entrar").disabled = true; $("entrar").textContent = "Validando…";
  try {
    const r = await fetch("/api/sesion", {method:"POST", headers:{"Content-Type":"application/json"},
      body: JSON.stringify({correo: $("correo").value, token: $("token").value})});
    const d = await r.json();
    if (!r.ok){ $("errorLogin").textContent = d.mensaje || "No se pudo iniciar sesión."; return; }
    sesion = {token: $("token").value.trim(), perfil: d}; $("token").value = ""; mostrarApp();
  } catch { $("errorLogin").textContent = "No se pudo conectar con el servidor. Si estaba dormido, espera un minuto y reintenta."; }
  finally { $("entrar").disabled = false; $("entrar").textContent = "Ingresar"; }
};

function mostrarApp(){
  const p = sesion.perfil;
  $("login").classList.add("oculto"); $("app").classList.remove("oculto");
  $("nombre").textContent = p.nombre; $("area").textContent = p.correo + " · " + p.area;
  $("rol").textContent = p.es_admin ? "Administrador" : "Consulta";
  $("avatar").textContent = p.nombre.split(" ").map(x => x[0]).join("").slice(0,2).toUpperCase();
  $("tablas").innerHTML = p.tablas.map(t => "<span>"+esc(t)+"</span>").join("");
  const lista = SUGERENCIAS[p.area] || SUGERENCIAS["_"];
  $("sugerencias").innerHTML = "";
  lista.forEach(q => { const b = document.createElement("button"); b.className = "sugerencia"; b.textContent = q;
    b.onclick = () => { $("pregunta").value = q; enviar(); }; $("sugerencias").appendChild(b); });
  $("mensajes").innerHTML = "<div class='bienvenida' id='bienvenida'>Hola, <b>"+esc(p.nombre.split(" ")[0])+"</b>. Pregunta en español por tus datos o elige una sugerencia de la izquierda.</div>";
  $("pregunta").focus();
}

$("salir").onclick = () => { sesion = null; $("app").classList.add("oculto"); $("login").classList.remove("oculto"); $("correo").focus(); };

async function enviar(){
  const q = $("pregunta").value.trim(); if (!q || !sesion) return;
  $("pregunta").value = ""; $("enviar").disabled = true;
  burbuja("yo", esc(q));
  const espera = burbuja("ia escribiendo", "Consultando los datos…");
  const inicio = performance.now();
  try {
    const r = await fetch("/api/asistente/preguntar", {method:"POST",
      headers:{"Content-Type":"application/json","Authorization":"Bearer " + sesion.token},
      body: JSON.stringify({pregunta: q})});
    const d = await r.json(); espera.remove();
    if (r.status === 401){ burbuja("ia", "Tu sesión no es válida. Vuelve a iniciar sesión."); return; }
    if (!r.ok){ burbuja("ia", "⚠️ " + esc(d.mensaje || ("Error " + r.status))); return; }
    const seg = ((performance.now() - inicio)/1000).toFixed(1);
    const chips = d.herramientas_usadas.map(u => "<span class='chip"+(u.ok?"":" mal")+"'>"+esc(u.herramienta)+"</span>").join("");
    burbuja("ia", formatear(d.respuesta) + "<div class='meta'>"+(chips || "sin herramientas")+"<span>· "+esc(d.modelo)+" · "+seg+" s</span></div>");
  } catch { espera.remove(); burbuja("ia", "No se pudo conectar con el servidor."); }
  finally { $("enviar").disabled = false; $("pregunta").focus(); }
}
$("formPregunta").onsubmit = (e) => { e.preventDefault(); enviar(); };
$("pregunta").addEventListener("keydown", (e) => { if (e.key === "Enter" && !e.shiftKey){ e.preventDefault(); enviar(); } });
</script></body></html>"""
