"""Pruebas del asistente con IA (Módulo 6 · S4). Sin red ni base de datos:
el LLM y el caso de uso se reemplazan por dobles."""

import json

import httpx
import pytest

from app.adaptadores.salida.groq import AsistenteNoConfigurado, ClienteGroq
from app.aplicacion.asistente import MAX_LARGO_PREGUNTA, Asistente
from app.dominio.errores import ParametroInvalido, ServicioNoDisponible, TablaNoAutorizada
from app.dominio.modelos import Canal, TipoConsulta, Usuario

USUARIO = Usuario("comercial@decor-demo.co", "Comercial", "Comercial", False, frozenset({"zventas"}))


def llamada(id_, nombre, argumentos):
    return {"id": id_, "type": "function", "function": {"name": nombre, "arguments": json.dumps(argumentos)}}


class LLMFalso:
    """Devuelve respuestas guionadas y guarda los mensajes que recibió."""

    modelo = "llm-falso"

    def __init__(self, respuestas):
        self._respuestas = list(respuestas)
        self.mensajes_recibidos = []

    def completar(self, mensajes, herramientas):
        self.mensajes_recibidos.append([dict(m) for m in mensajes])
        return self._respuestas.pop(0)


class CasoUsoFalso:
    def __init__(self):
        self.llamadas = []

    def consultar_sql(self, usuario, canal, sql, tipo):
        self.llamadas.append((canal, sql, tipo))
        if "mv_clientes" in sql:
            raise TablaNoAutorizada("La tabla 'mv_clientes' no está habilitada para este usuario.")
        return {"columnas": ["vkbur", "facturas"], "filas": [{"vkbur": "BOG1", "facturas": 42}], "total_filas": 1}

    def guia_negocio(self, usuario, canal, tabla=None):
        self.llamadas.append((canal, "guia", None))
        return {"tablas_permitidas": {"zventas": "Facturas"}}


def test_respuesta_directa_sin_herramientas():
    asistente = Asistente(CasoUsoFalso(), LLMFalso([{"content": "Hola, ¿en qué te ayudo?"}]))
    r = asistente.preguntar(USUARIO, "hola")
    assert r["respuesta"] == "Hola, ¿en qué te ayudo?"
    assert r["herramientas_usadas"] == [] and r["modelo"] == "llm-falso"


def test_usa_herramienta_y_responde_con_el_dato():
    caso = CasoUsoFalso()
    llm = LLMFalso([
        {"content": None, "tool_calls": [llamada("c1", "query_analytics", {"sql": "SELECT vkbur, count(*) FROM zventas GROUP BY 1"})]},
        {"content": "BOG1 emitió 42 facturas."},
    ])
    r = Asistente(caso, llm).preguntar(USUARIO, "¿Cuántas facturas por oficina?")
    assert r["respuesta"] == "BOG1 emitió 42 facturas."
    assert r["herramientas_usadas"] == [{"herramienta": "query_analytics", "ok": True}]
    # Pasa por el MISMO caso de uso, con canal ASISTENTE y límites de analítica
    assert caso.llamadas[0][0] == Canal.ASISTENTE and caso.llamadas[0][2] == TipoConsulta.ANALITICA
    # El resultado de la herramienta vuelve al LLM con el id de la llamada
    mensaje_tool = llm.mensajes_recibidos[1][-1]
    assert mensaje_tool["role"] == "tool" and mensaje_tool["tool_call_id"] == "c1" and "42" in mensaje_tool["content"]


def test_error_de_politica_se_devuelve_al_llm_no_al_usuario():
    llm = LLMFalso([
        {"content": None, "tool_calls": [llamada("c1", "query_table", {"sql": "SELECT correo FROM mv_clientes"})]},
        {"content": "No tienes permiso para ver datos de clientes."},
    ])
    r = Asistente(CasoUsoFalso(), llm).preguntar(USUARIO, "Dame los correos de los clientes")
    assert r["herramientas_usadas"] == [{"herramienta": "query_table", "ok": False}]
    assert "TABLA_NO_AUTORIZADA" in llm.mensajes_recibidos[1][-1]["content"]


def test_herramienta_desconocida_y_argumentos_invalidos_no_rompen():
    llm = LLMFalso([
        {"content": None, "tool_calls": [llamada("c1", "drop_database", {}),
                                         {"id": "c2", "type": "function", "function": {"name": "query_table", "arguments": "{no json"}}]},
        {"content": "No puedo hacer eso."},
    ])
    r = Asistente(CasoUsoFalso(), llm).preguntar(USUARIO, "borra todo")
    assert [u["ok"] for u in r["herramientas_usadas"]] == [False, False]


def test_corta_tras_el_maximo_de_pasos():
    bucle = {"content": None, "tool_calls": [llamada("c", "business_guide", {})]}
    r = Asistente(CasoUsoFalso(), LLMFalso([bucle] * 3), max_pasos=3).preguntar(USUARIO, "?")
    assert "máximo de pasos" in r["respuesta"] and len(r["herramientas_usadas"]) == 3


@pytest.mark.parametrize("pregunta", ["", "   ", "x" * (MAX_LARGO_PREGUNTA + 1)])
def test_pregunta_vacia_o_muy_larga_es_rechazada(pregunta):
    with pytest.raises(ParametroInvalido):
        Asistente(CasoUsoFalso(), LLMFalso([])).preguntar(USUARIO, pregunta)


def test_sin_llave_responde_servicio_no_disponible():
    with pytest.raises(ServicioNoDisponible, match="GROQ_API_KEY"):
        Asistente(CasoUsoFalso(), AsistenteNoConfigurado()).preguntar(USUARIO, "hola")


def _groq_con(respuesta):
    enviados = []

    def manejador(request):
        enviados.append(request)
        return respuesta(request)

    return ClienteGroq("llave-de-prueba", cliente_http=httpx.Client(transport=httpx.MockTransport(manejador))), enviados


def test_cliente_groq_envia_llave_y_herramientas():
    groq, enviados = _groq_con(lambda req: httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]}))
    assert groq.completar([{"role": "user", "content": "hola"}], [{"type": "function"}]) == {"content": "ok"}
    assert enviados[0].headers["Authorization"] == "Bearer llave-de-prueba"
    cuerpo = json.loads(enviados[0].content)
    assert cuerpo["model"] == "llama-3.3-70b-versatile" and cuerpo["tools"] == [{"type": "function"}]


@pytest.mark.parametrize("estado", [401, 429, 500])
def test_cliente_groq_traduce_errores_a_servicio_no_disponible(estado):
    groq, _ = _groq_con(lambda req: httpx.Response(estado, json={}))
    with pytest.raises(ServicioNoDisponible):
        groq.completar([], [])
