"""Caso de uso «Preguntar al asistente» (función con IA del Módulo 6).

El colaborador escribe una pregunta en español. Un LLM (Groq) decide qué
herramientas usar; cada herramienta se ejecuta con el MISMO caso de uso
«Ejecutar consulta», así que la Política de acceso, los límites y la auditoría
se aplican igual que por MCP o REST. El LLM nunca toca la base de datos.
"""

from __future__ import annotations

import json
from typing import Any, Callable, Protocol

from app.aplicacion.ejecutar_consulta import EjecutarConsulta
from app.dominio.errores import ErrorDecor, ParametroInvalido
from app.dominio.modelos import Canal, TipoConsulta, Usuario

MAX_LARGO_PREGUNTA = 500
MAX_PASOS = 6
MAX_CARACTERES_RESULTADO = 6000
# Los parámetros opcionales aceptan null: algunos modelos los envían así y Groq valida el esquema.

INSTRUCCIONES_SISTEMA = (
    "Eres el asistente de datos de Grupo Decor (MVP con datos ficticios). Respondes en español, "
    "de forma breve y con las cifras exactas que devuelven las herramientas. "
    "Primero llama a business_guide para conocer las tablas permitidas, las claves de unión y las reglas "
    "del negocio (por ejemplo: en zventas, erdat es texto AAAAMMDD y netwr es texto). "
    "Usa query_analytics para conteos y sumas, y query_table solo para detalle. "
    "Si una herramienta devuelve un error, corrige la consulta o explica al usuario por qué no se puede. "
    "Nunca inventes datos: si no los obtuviste de una herramienta, dilo."
)


class ProveedorLLM(Protocol):
    """Puerto de salida hacia el modelo de lenguaje (formato de mensajes tipo OpenAI)."""

    modelo: str

    def completar(self, mensajes: list[dict[str, Any]], herramientas: list[dict[str, Any]]) -> dict[str, Any]:
        """Devuelve el mensaje del asistente: {"content": str | None, "tool_calls": [...]}."""
        ...


def _herramienta(nombre: str, descripcion: str, propiedades: dict[str, Any] | None = None,
                 requeridas: list[str] | None = None) -> dict[str, Any]:
    return {"type": "function", "function": {
        "name": nombre, "description": descripcion,
        "parameters": {"type": "object", "properties": propiedades or {}, "required": requeridas or []}}}


_TABLA = {"table": {"type": "string", "description": "Nombre de la tabla"}}
_SQL = {"sql": {"type": "string", "description": "Una sola sentencia SELECT o WITH"}}

HERRAMIENTAS: list[dict[str, Any]] = [
    _herramienta("business_guide", "Mapa del negocio y tablas permitidas para el usuario. Llamar primero.",
                 {"table": {"type": ["string", "null"], "description": "Opcional: detalle de una tabla"}}),
    _herramienta("list_tables", "Lista las tablas permitidas y sus columnas."),
    _herramienta("describe_table", "Columnas, tipos y descripciones de una tabla.", _TABLA, ["table"]),
    _herramienta("sample_rows", "Filas de ejemplo de una tabla (1 a 50).",
                 {**_TABLA, "limit": {"type": ["integer", "null"], "description": "1 a 50"}}, ["table"]),
    _herramienta("count_rows", "Conteo de filas con filtro de igualdad opcional (column = value).",
                 {**_TABLA, "column": {"type": ["string", "null"]}, "value": {"type": ["string", "null"]}}, ["table"]),
    _herramienta("list_distinct", "Valores distintos de una columna y su frecuencia.",
                 {**_TABLA, "column": {"type": "string"}}, ["table", "column"]),
    _herramienta("query_table", "SQL de DETALLE (solo SELECT/WITH). Máximo 2.000 filas.", _SQL, ["sql"]),
    _herramienta("query_analytics", "SQL de AGREGADOS (GROUP BY, SUM, COUNT). Máximo 500 filas y 15 s.",
                 _SQL, ["sql"]),
]


class Asistente:
    def __init__(self, caso_uso: EjecutarConsulta, llm: ProveedorLLM, max_pasos: int = MAX_PASOS):
        self._caso_uso = caso_uso
        self._llm = llm
        self._max_pasos = max_pasos

    def preguntar(self, usuario: Usuario, pregunta: str) -> dict[str, Any]:
        pregunta = (pregunta or "").strip()
        if not pregunta:
            raise ParametroInvalido("La pregunta no puede estar vacía.")
        if len(pregunta) > MAX_LARGO_PREGUNTA:
            raise ParametroInvalido(f"La pregunta supera {MAX_LARGO_PREGUNTA} caracteres.")

        mensajes: list[dict[str, Any]] = [
            {"role": "system", "content": INSTRUCCIONES_SISTEMA},
            {"role": "user", "content": pregunta},
        ]
        usadas: list[dict[str, Any]] = []

        for _ in range(self._max_pasos):
            respuesta = self._llm.completar(mensajes, HERRAMIENTAS)
            llamadas = respuesta.get("tool_calls") or []
            if not llamadas:
                return {"pregunta": pregunta, "respuesta": (respuesta.get("content") or "").strip(),
                        "herramientas_usadas": usadas, "modelo": self._llm.modelo}

            mensajes.append({"role": "assistant", "content": respuesta.get("content") or "", "tool_calls": llamadas})
            for llamada in llamadas:
                nombre = llamada["function"]["name"]
                resultado, ok = self._ejecutar_herramienta(usuario, nombre, llamada["function"].get("arguments"))
                usadas.append({"herramienta": nombre, "ok": ok})
                mensajes.append({"role": "tool", "tool_call_id": llamada["id"], "content": resultado})

        return {"pregunta": pregunta,
                "respuesta": "No logré responder en el número máximo de pasos. Intenta una pregunta más concreta.",
                "herramientas_usadas": usadas, "modelo": self._llm.modelo}

    # ------------------------------------------------------------------ privados
    def _ejecutar_herramienta(self, usuario: Usuario, nombre: str, argumentos_json: str | None) -> tuple[str, bool]:
        """Ejecuta la herramienta pedida por el LLM. Los errores se devuelven al LLM como texto
        (igual que isError en MCP) para que pueda corregir la consulta."""
        try:
            argumentos = json.loads(argumentos_json or "{}")
            if not isinstance(argumentos, dict):
                raise ValueError
        except ValueError:
            return json.dumps({"error": "PARAMETRO_INVALIDO", "mensaje": "Argumentos no son JSON válido."}), False

        accion = self._acciones(usuario).get(nombre)
        if accion is None:
            return json.dumps({"error": "HERRAMIENTA_DESCONOCIDA", "mensaje": nombre}), False
        try:
            datos = accion(argumentos)
        except ErrorDecor as error:
            return json.dumps({"error": error.codigo, "mensaje": error.mensaje}, ensure_ascii=False), False
        except (TypeError, KeyError, ValueError) as error:
            return json.dumps({"error": "PARAMETRO_INVALIDO", "mensaje": str(error)}, ensure_ascii=False), False
        texto = json.dumps(datos, ensure_ascii=False, default=str)
        if len(texto) > MAX_CARACTERES_RESULTADO:
            texto = texto[:MAX_CARACTERES_RESULTADO] + " …[resultado recortado]"
        return texto, True

    def _acciones(self, usuario: Usuario) -> dict[str, Callable[[dict[str, Any]], Any]]:
        c, canal = self._caso_uso, Canal.ASISTENTE
        return {
            "business_guide": lambda a: c.guia_negocio(usuario, canal, a.get("table")),
            "list_tables": lambda a: c.listar_tablas(usuario, canal),
            "describe_table": lambda a: c.describir_tabla(usuario, canal, a["table"]),
            "sample_rows": lambda a: c.muestra_filas(usuario, canal, a["table"], int(a.get("limit") or 10)),
            "count_rows": lambda a: c.contar_filas(usuario, canal, a["table"], a.get("column"), a.get("value")),
            "list_distinct": lambda a: c.valores_distintos(usuario, canal, a["table"], a["column"]),
            "query_table": lambda a: c.consultar_sql(usuario, canal, a["sql"], TipoConsulta.DETALLE),
            "query_analytics": lambda a: c.consultar_sql(usuario, canal, a["sql"], TipoConsulta.ANALITICA),
        }
