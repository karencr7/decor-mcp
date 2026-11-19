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
:root{--ink:#1B2430;--ink2:#2B3A50;--paper:#F7F5F0;--card:#FFFFFF;--accent:#B5472F;--accent2:#9C3C27;--gold:#E3A84E;--muted:#5B6575;--line:#E4DED3;--soft:#FBF7F0;--bad:#B42318;--okbg:#E7F3EC;--ok:#22704B}
*{box-sizing:border-box}
body{margin:0;font-family:system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;color:var(--ink);background:var(--paper)}
button{font:inherit}
.oculto{display:none!important}
/* ================= INICIO DE SESIÓN ================= */
#login{min-height:100vh;display:grid;grid-template-columns:minmax(320px,0.9fr) 1.1fr}
.marca{background:linear-gradient(155deg,var(--ink) 0%,var(--ink2) 65%,var(--accent) 150%);color:#F7F5F0;padding:48px;display:flex;flex-direction:column;justify-content:space-between;gap:32px}
.logo{display:flex;align-items:center;gap:12px;font-weight:700;font-size:20px}
.logo i{font-style:normal;width:40px;height:40px;border-radius:10px;background:var(--gold);color:var(--ink);display:grid;place-items:center}
.marca h1{font-size:40px;line-height:1.1;margin:0 0 14px}
.marca p{color:#C9D3DE;font-size:16px;line-height:1.55;margin:0}
.garantias{display:grid;gap:12px;margin-top:26px}
.garantias div{display:flex;gap:12px;align-items:center;font-size:15px;color:#DCE3EA}
.garantias span{width:30px;height:30px;border-radius:8px;background:rgba(227,168,78,.18);display:grid;place-items:center;flex:none}
.formulario{display:grid;place-items:center;padding:32px 24px}
.caja{width:100%;max-width:480px}
.caja h2{margin:0 0 6px;font-size:28px}
.caja .sub{margin:0 0 26px;color:var(--muted)}
.paso{display:flex;align-items:center;gap:10px;font-weight:700;margin:0 0 12px}
.paso b{width:26px;height:26px;border-radius:50%;background:var(--ink);color:#fff;display:grid;place-items:center;font-size:13px}
.perfiles{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-bottom:10px}
.perfil{background:var(--card);border:2px solid var(--line);border-radius:14px;padding:14px 10px;text-align:center;cursor:pointer;transition:border-color .15s,transform .15s}
.perfil:hover{transform:translateY(-2px)}
.perfil .ico{font-size:26px}
.perfil strong{display:block;margin-top:6px;font-size:15px}
.perfil small{display:block;color:var(--muted);font-size:12px;margin-top:3px;line-height:1.35}
.perfil.activo{border-color:var(--accent);background:#FFF6F1;box-shadow:0 0 0 3px rgba(181,71,47,.12)}
.otro{background:none;border:0;color:var(--accent);cursor:pointer;padding:4px 0;font-size:14px;text-decoration:underline}
input{width:100%;padding:13px 14px;border:1.5px solid #CFC8BB;border-radius:12px;font:inherit;background:#FFFDF9}
input:focus,textarea:focus{outline:3px solid rgba(227,168,78,.45);border-color:var(--gold)}
#bloqueCorreo{margin:8px 0 4px}
.campo{position:relative;margin-top:2px}
.campo button{position:absolute;right:8px;top:8px;border:0;background:var(--soft);color:var(--ink);cursor:pointer;font-size:13px;padding:6px 10px;border-radius:8px}
.ayuda{font-size:13px;color:var(--muted);margin:8px 0 0;line-height:1.45}
.bloque{margin-top:26px}
.entrar{width:100%;margin-top:24px;padding:15px;border:0;border-radius:12px;background:var(--accent);color:#fff;font-weight:700;font-size:16px;cursor:pointer}
.entrar:hover{background:var(--accent2)}
.entrar:disabled{opacity:.55;cursor:not-allowed}
.error{margin-top:14px;padding:12px 14px;border-radius:10px;background:#FDECEA;color:var(--bad);font-size:14px}
/* ================= APLICACIÓN ================= */
#app{height:100vh;display:grid;grid-template-rows:auto 1fr auto}
header{background:var(--ink);color:#F7F5F0;padding:12px 24px;display:flex;align-items:center;gap:16px}
header .logo{font-size:17px}header .logo i{width:32px;height:32px}
.espacio{flex:1}
.quien{display:flex;align-items:center;gap:10px;background:#263243;border-radius:999px;padding:5px 14px 5px 5px}
.avatar{width:32px;height:32px;border-radius:50%;background:var(--gold);color:var(--ink);display:grid;place-items:center;font-weight:700;font-size:13px}
.quien small{display:block;color:#AEBBCB;font-size:12px}
.hbtn{background:transparent;color:#F7F5F0;border:1px solid #4A5B73;border-radius:10px;padding:8px 14px;cursor:pointer}
.hbtn:hover{background:#263243}
.conversacion{overflow-y:auto;padding:28px 20px}
.ancho{max-width:860px;margin:0 auto;display:flex;flex-direction:column;gap:18px}
.inicio{text-align:center;padding:24px 0 8px}
.inicio h2{font-size:30px;margin:0 0 8px}
.inicio p{color:var(--muted);margin:0 0 22px}
.permisos{display:inline-flex;align-items:center;gap:8px;background:var(--okbg);color:var(--ok);padding:7px 14px;border-radius:999px;font-size:14px;cursor:pointer;border:0}
.listaTablas{display:flex;flex-wrap:wrap;gap:6px;justify-content:center;margin-top:12px}
.listaTablas span{font-size:12.5px;background:#EEF2F6;border-radius:6px;padding:4px 9px;font-family:ui-monospace,monospace}
.tarjetas{display:grid;grid-template-columns:repeat(2,1fr);gap:12px;margin-top:26px;text-align:left}
.tarjeta{background:var(--card);border:1.5px solid var(--line);border-radius:14px;padding:16px 18px;cursor:pointer;display:flex;gap:12px;align-items:flex-start;transition:border-color .15s,transform .15s;color:var(--ink);text-align:left}
.tarjeta:hover{border-color:var(--gold);transform:translateY(-2px)}
.tarjeta .ico{font-size:22px}
.tarjeta strong{display:block;font-size:15px;line-height:1.35}
.tarjeta small{color:var(--muted);font-size:12.5px}
.msg{display:flex;gap:12px;align-items:flex-start}
.msg.yo{flex-direction:row-reverse}
.msg .quienes{width:34px;height:34px;border-radius:50%;display:grid;place-items:center;font-weight:700;font-size:13px;flex:none}
.msg.yo .quienes{background:var(--gold);color:var(--ink)}
.msg.ia .quienes{background:var(--ink);color:var(--gold)}
.burbuja{max-width:80%;padding:14px 18px;border-radius:16px;line-height:1.6;font-size:15.5px}
.yo .burbuja{background:var(--ink);color:#F7F5F0;border-top-right-radius:4px}
.ia .burbuja{background:var(--card);border:1px solid var(--line);border-top-left-radius:4px;box-shadow:0 2px 10px rgba(27,36,48,.04)}
.ia table{border-collapse:collapse;margin:10px 0;font-size:14.5px;min-width:240px}
.ia th,.ia td{border-bottom:1px solid var(--line);padding:7px 12px;text-align:left}
.ia th{background:var(--soft);font-weight:700}
.ia td:last-child,.ia th:last-child{text-align:right}
.ia code{background:#F0EBE2;padding:1px 6px;border-radius:5px;font-size:13px}
.pasos{margin-top:12px;padding-top:10px;border-top:1px dashed var(--line);display:flex;flex-wrap:wrap;gap:6px;align-items:center;font-size:12.5px;color:var(--muted)}
.chip{padding:3px 10px;border-radius:999px;background:#E8EEF7;color:#24426B;font-weight:600;cursor:help}
.chip.mal{background:#FDECEA;color:var(--bad)}
.pensando{display:flex;align-items:center;gap:10px;color:var(--muted);font-size:15px}
.puntos{display:inline-flex;gap:4px}.puntos i{width:7px;height:7px;border-radius:50%;background:var(--gold);animation:salto 1s infinite}
.puntos i:nth-child(2){animation-delay:.15s}.puntos i:nth-child(3){animation-delay:.3s}
@keyframes salto{0%,80%,100%{opacity:.3;transform:translateY(0)}40%{opacity:1;transform:translateY(-4px)}}
.aviso{background:#FFF6E5;border:1px solid #F1D9A8}
footer{background:linear-gradient(to top,var(--paper) 70%,rgba(247,245,240,0));padding:12px 20px 18px}
.barra{max-width:860px;margin:0 auto;display:flex;gap:10px;align-items:flex-end;background:var(--card);border:1.5px solid var(--line);border-radius:18px;padding:8px 8px 8px 16px;box-shadow:0 6px 24px rgba(27,36,48,.08)}
.barra:focus-within{border-color:var(--gold)}
.barra textarea{flex:1;border:0;resize:none;font:inherit;font-size:15.5px;padding:9px 0;max-height:140px;background:transparent;outline:none}
.enviar{width:44px;height:44px;border-radius:12px;border:0;background:var(--accent);color:#fff;font-size:20px;cursor:pointer;flex:none}
.enviar:disabled{opacity:.45;cursor:not-allowed}
.nota{max-width:860px;margin:8px auto 0;font-size:12px;color:var(--muted);text-align:center}
@media (max-width:860px){
 #login{grid-template-columns:1fr}.marca{padding:24px 22px;gap:14px}.marca h1{font-size:26px}.marca p,.garantias{display:none}
 .perfiles{grid-template-columns:1fr}.perfil{display:flex;align-items:center;gap:12px;text-align:left}.perfil strong{margin:0}
 .tarjetas{grid-template-columns:1fr}.quien small,.logo b{display:none}.burbuja{max-width:100%}header{padding:10px 14px;gap:8px}
}
</style></head><body>

<!-- ================= INICIO DE SESIÓN ================= -->
<section id="login">
  <div class="marca">
    <div class="logo"><i>D</i><b>Decor MCP</b></div>
    <div>
      <h1>Pregunta por tus datos, en español.</h1>
      <p>Ventas, pedidos, cartera y existencias de Grupo Decor, respondidas con cifras reales y solo con los permisos de tu usuario.</p>
      <div class="garantias">
        <div><span>🔒</span>Solo lectura: nadie puede modificar ni borrar datos.</div>
        <div><span>👤</span>Cada usuario ve únicamente sus tablas autorizadas.</div>
        <div><span>📋</span>Cada consulta queda registrada en la auditoría.</div>
      </div>
    </div>
    <small style="color:#9FB0C3">MVP con datos ficticios · Ley 1581 de 2012</small>
  </div>

  <div class="formulario">
    <form class="caja" id="formLogin" autocomplete="off">
      <h2>Bienvenido</h2>
      <p class="sub">Entra en dos pasos.</p>

      <p class="paso"><b>1</b> ¿Con qué usuario entras?</p>
      <div class="perfiles" id="perfiles">
        <button type="button" class="perfil" data-correo="comercial@decor-demo.co"><div class="ico">🧾</div><div><strong>Comercial</strong><small>Ventas, pedidos y existencias</small></div></button>
        <button type="button" class="perfil" data-correo="cartera@decor-demo.co"><div class="ico">💳</div><div><strong>Cartera</strong><small>Cartera y facturas</small></div></button>
        <button type="button" class="perfil" data-correo="admin@decor-demo.co"><div class="ico">🛡️</div><div><strong>Administrador</strong><small>Todo + auditoría</small></div></button>
      </div>
      <button type="button" class="otro" id="otro">Usar otro correo</button>
      <div id="bloqueCorreo" class="oculto">
        <input id="correo" type="email" placeholder="tu.correo@empresa.co" aria-label="Usuario (correo)">
      </div>

      <div class="bloque">
        <p class="paso"><b>2</b> Pega tu token</p>
        <div class="campo"><input id="token" type="password" placeholder="Token de acceso" aria-label="Token"><button type="button" id="ver">Mostrar</button></div>
        <p class="ayuda">Es como tu contraseña: te lo entrega TI. En la demo está en Render → Environment → <code>DECOR_TOKEN_…</code></p>
      </div>

      <button class="entrar" id="entrar" type="submit" disabled>Entrar</button>
      <div class="error oculto" id="errorLogin" role="alert"></div>
    </form>
  </div>
</section>

<!-- ================= APLICACIÓN ================= -->
<section id="app" class="oculto">
  <header>
    <div class="logo"><i>D</i><b>Decor MCP</b></div>
    <div class="espacio"></div>
    <button class="hbtn" id="nueva">＋ Nueva conversación</button>
    <div class="quien"><div class="avatar" id="avatar"></div><div><b id="nombre"></b><small id="rol"></small></div></div>
    <button class="hbtn" id="salir">Salir</button>
  </header>

  <div class="conversacion" id="conversacion"><div class="ancho" id="mensajes"></div></div>

  <footer>
    <form class="barra" id="formPregunta">
      <textarea id="pregunta" rows="1" maxlength="500" placeholder="Escribe tu pregunta… por ejemplo: ¿cuántas facturas hubo en septiembre?"></textarea>
      <button class="enviar" id="enviar" type="submit" title="Enviar" disabled>➤</button>
    </form>
    <p class="nota">Enter para enviar · Shift + Enter para nueva línea · Las respuestas salen de la base con tus permisos</p>
  </footer>
</section>

<script>
const $ = (id) => document.getElementById(id);
let sesion = null; // el token vive solo en memoria: se borra al cerrar la pestaña

const PREGUNTAS = {
  "Comercial": [["📊","¿Cuántas facturas emitió cada oficina en septiembre de 2026?","Totales por oficina"],["📦","¿Cuántos pedidos están abiertos y cuánto suman?","Estado de pedidos"],["🏭","¿Cuál es el material con más existencias en Decorcerámica?","Inventario"],["🔒","Muéstrame el correo de los clientes","Prueba de seguridad"]],
  "Cartera": [["💳","¿Qué clientes tienen más cartera vencida?","Cartera"],["📅","¿Cuánto suma la cartera vencida a octubre de 2026?","Totales"],["🧾","¿Cuántas facturas se emitieron en septiembre de 2026?","Facturación"],["🔒","¿Cuántos pedidos hay abiertos?","Prueba de seguridad"]],
  "_": [["🗂️","¿Qué tablas puedo consultar y qué contienen?","Conocer los datos"],["📊","¿Cuántas facturas emitió cada oficina en septiembre de 2026?","Totales por oficina"],["📨","¿Cuántas PQR abiertas hay por oficina?","Servicio al cliente"],["⭐","¿Cuántos socios DecorClub hay por nivel?","Fidelización"]]
};
const HERRAMIENTAS = {
  business_guide:["Guía del negocio","Revisó qué tablas puedes ver y las reglas del negocio"],
  list_tables:["Lista de tablas","Listó tus tablas autorizadas"],
  describe_table:["Columnas","Revisó las columnas de una tabla"],
  sample_rows:["Filas de ejemplo","Miró algunas filas de ejemplo"],
  count_rows:["Conteo","Contó registros"],
  list_distinct:["Valores distintos","Revisó los valores posibles de una columna"],
  query_table:["Consulta de detalle","Consultó registros (máx. 2.000 filas)"],
  query_analytics:["Consulta de totales","Calculó totales y agrupaciones (máx. 500 filas, 15 s)"]
};
const ESTADOS = ["Revisando tus permisos…","Buscando la tabla correcta…","Consultando la base de datos…","Preparando la respuesta…"];

const esc = (t) => String(t).replace(/[&<>"']/g, (c) => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const enLinea = (t) => esc(t).replace(/\*\*(.+?)\*\*/g,"<b>$1</b>").replace(/`([^`]+)`/g,"<code>$1</code>");
function formatear(texto){
  const l = texto.split("\n"); let h = ""; let i = 0; const esFila = (s) => /^\s*\|.*\|\s*$/.test(s);
  while (i < l.length){
    if (esFila(l[i])){
      const filas = []; while (i < l.length && esFila(l[i])) filas.push(l[i++]);
      const datos = filas.filter(f => !/^\s*\|[\s:\-|]+\|\s*$/.test(f)).map(f => f.trim().replace(/^\||\|$/g,"").split("|").map(c => c.trim()));
      if (datos.length){ h += "<table><tr>"+datos[0].map(c=>"<th>"+enLinea(c)+"</th>").join("")+"</tr>"; datos.slice(1).forEach(r => h += "<tr>"+r.map(c=>"<td>"+enLinea(c)+"</td>").join("")+"</tr>"); h += "</table>"; }
      continue;
    }
    h += l[i].trim() ? (/^\s*[-*] /.test(l[i]) ? "<div>• "+enLinea(l[i].replace(/^\s*[-*] /,""))+"</div>" : "<div>"+enLinea(l[i])+"</div>") : "<div style='height:6px'></div>";
    i++;
  }
  return h;
}
const iniciales = (n) => n.replace(/\(.*?\)/g,"").trim().split(/\s+/).map(x => x[0]).join("").slice(0,2).toUpperCase();

/* ---------- inicio de sesión ---------- */
function validarLogin(){ $("entrar").disabled = !($("correo").value.trim() && $("token").value.trim()); }
document.querySelectorAll(".perfil").forEach(b => b.onclick = () => {
  document.querySelectorAll(".perfil").forEach(x => x.classList.remove("activo")); b.classList.add("activo");
  $("correo").value = b.dataset.correo; $("bloqueCorreo").classList.add("oculto"); validarLogin(); $("token").focus();
});
$("otro").onclick = () => { document.querySelectorAll(".perfil").forEach(x => x.classList.remove("activo")); $("correo").value = ""; $("bloqueCorreo").classList.remove("oculto"); $("correo").focus(); validarLogin(); };
$("correo").oninput = validarLogin; $("token").oninput = validarLogin;
$("ver").onclick = () => { const t = $("token"); t.type = t.type === "password" ? "text" : "password"; $("ver").textContent = t.type === "password" ? "Mostrar" : "Ocultar"; };

$("formLogin").onsubmit = async (e) => {
  e.preventDefault(); $("errorLogin").classList.add("oculto"); $("entrar").disabled = true; $("entrar").textContent = "Verificando…";
  try {
    const r = await fetch("/api/sesion", {method:"POST", headers:{"Content-Type":"application/json"}, body: JSON.stringify({correo: $("correo").value, token: $("token").value})});
    const d = await r.json();
    if (!r.ok){ mostrarError(r.status === 401 ? "Usuario o token incorrectos. Revisa que el token sea el de ese usuario." : (d.mensaje || "No se pudo iniciar sesión.")); return; }
    sesion = {token: $("token").value.trim(), perfil: d}; $("token").value = ""; abrirApp();
  } catch { mostrarError("No hay conexión con el servidor. Si estuvo inactivo, tarda cerca de un minuto en despertar: intenta de nuevo."); }
  finally { $("entrar").textContent = "Entrar"; validarLogin(); }
};
function mostrarError(t){ $("errorLogin").textContent = t; $("errorLogin").classList.remove("oculto"); }

/* ---------- aplicación ---------- */
function abrirApp(){
  const p = sesion.perfil;
  $("login").classList.add("oculto"); $("app").classList.remove("oculto");
  $("avatar").textContent = iniciales(p.nombre); $("nombre").textContent = p.nombre.replace(/\s*\(demo\)/,"");
  $("rol").textContent = (p.es_admin ? "Administrador · " : "") + p.area;
  inicio();
}
function inicio(){
  const p = sesion.perfil; const lista = PREGUNTAS[p.area] || PREGUNTAS["_"];
  $("mensajes").innerHTML = `<div class="inicio">
      <h2>Hola 👋 ¿qué quieres saber hoy?</h2>
      <p>Entraste como <b>${esc(p.area)}</b>. Toca una pregunta o escribe la tuya abajo.</p>
      <button class="permisos" id="verTablas">✔ Puedes consultar ${p.tablas.length} tablas · ver cuáles</button>
      <div class="listaTablas oculto" id="listaTablas">${p.tablas.map(t => "<span>"+esc(t)+"</span>").join("")}</div>
      <div class="tarjetas">${lista.map(([ico,q,tema]) => `<button class="tarjeta" data-q="${esc(q)}"><span class="ico">${ico}</span><span><small>${esc(tema)}</small><strong>${esc(q)}</strong></span></button>`).join("")}</div>
    </div>`;
  $("verTablas").onclick = () => $("listaTablas").classList.toggle("oculto");
  document.querySelectorAll(".tarjeta").forEach(b => b.onclick = () => { $("pregunta").value = b.dataset.q; enviar(); });
  $("pregunta").focus();
}
function agregar(quien, html, clase){
  const d = document.createElement("div"); d.className = "msg " + quien;
  d.innerHTML = `<div class="quienes">${quien === "yo" ? esc(iniciales(sesion.perfil.nombre)) : "IA"}</div><div class="burbuja ${clase||""}">${html}</div>`;
  $("mensajes").appendChild(d); $("conversacion").scrollTop = $("conversacion").scrollHeight; return d;
}
async function enviar(){
  const q = $("pregunta").value.trim(); if (!q || !sesion) return;
  document.querySelector(".inicio")?.remove();
  $("pregunta").value = ""; ajustar(); $("enviar").disabled = true;
  agregar("yo", esc(q));
  const espera = agregar("ia", `<div class="pensando"><span class="puntos"><i></i><i></i><i></i></span><span id="estado">${ESTADOS[0]}</span></div>`);
  let k = 0; const reloj = setInterval(() => { const e = espera.querySelector("#estado"); if (e) e.textContent = ESTADOS[Math.min(++k, ESTADOS.length-1)]; }, 1600);
  const t0 = performance.now();
  try {
    const r = await fetch("/api/asistente/preguntar", {method:"POST", headers:{"Content-Type":"application/json","Authorization":"Bearer " + sesion.token}, body: JSON.stringify({pregunta: q})});
    const d = await r.json(); clearInterval(reloj); espera.remove();
    if (r.status === 401){ agregar("ia", "Tu sesión ya no es válida. Toca <b>Salir</b> y vuelve a entrar.", "aviso"); return; }
    if (!r.ok){ agregar("ia", "⚠️ " + esc(d.mensaje || ("Error " + r.status)), "aviso"); return; }
    const pasos = d.herramientas_usadas.map(u => { const [n, t] = HERRAMIENTAS[u.herramienta] || [u.herramienta, ""];
      return `<span class="chip${u.ok ? "" : " mal"}" title="${esc((u.ok ? t : "Bloqueado: fuera de tus permisos o con error") + " (" + u.herramienta + ")")}">${u.ok ? "" : "⛔ "}${esc(n)}</span>`; }).join("");
    agregar("ia", formatear(d.respuesta) + `<div class="pasos">${pasos ? "Cómo lo obtuvo:" + pasos : "Respondió sin consultar la base"}<span>· ${((performance.now()-t0)/1000).toFixed(1)} s</span></div>`);
  } catch { clearInterval(reloj); espera.remove(); agregar("ia", "No hay conexión con el servidor. Intenta de nuevo en un momento.", "aviso"); }
  finally { $("enviar").disabled = !$("pregunta").value.trim(); $("pregunta").focus(); }
}
function ajustar(){ const t = $("pregunta"); t.style.height = "auto"; t.style.height = Math.min(t.scrollHeight, 140) + "px"; $("enviar").disabled = !t.value.trim(); }
$("pregunta").addEventListener("input", ajustar);
$("pregunta").addEventListener("keydown", (e) => { if (e.key === "Enter" && !e.shiftKey){ e.preventDefault(); enviar(); } });
$("formPregunta").onsubmit = (e) => { e.preventDefault(); enviar(); };
$("nueva").onclick = () => inicio();
$("salir").onclick = () => { sesion = null; $("app").classList.add("oculto"); $("login").classList.remove("oculto"); validarLogin(); };
</script></body></html>"""
