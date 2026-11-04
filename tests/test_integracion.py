"""Pruebas de integración contra PostgreSQL REAL (REST y MCP).

Se ejecutan solo si existen las variables DECOR_DB_LECTOR_URL, DECOR_DB_APP_URL
y DECOR_TOKEN_COMERCIAL / DECOR_TOKEN_ADMIN (por ejemplo, con la base de Docker
levantada). Si no están, pytest las marca como omitidas (skipped).
"""

import json
import os

import pytest

REQUERIDAS = ["DECOR_DB_LECTOR_URL", "DECOR_DB_APP_URL", "DECOR_TOKEN_COMERCIAL", "DECOR_TOKEN_ADMIN"]
pytestmark = pytest.mark.skipif(any(not os.getenv(v) for v in REQUERIDAS),
                                reason="Requiere PostgreSQL con los datos de demostración")


@pytest.fixture(scope="module")
def cliente():
    from fastapi.testclient import TestClient

    from app.main import crear_app

    with TestClient(crear_app(), base_url="http://localhost:8000") as c:
        yield c


def cabecera(variable):
    return {"Authorization": f"Bearer {os.environ[variable]}"}


def test_salud(cliente):
    assert cliente.get("/api/salud").json() == {"estado": "ok", "base_datos": "ok"}


def test_401_sin_token(cliente):
    assert cliente.get("/api/tablas").status_code == 401


def test_200_consulta_analitica(cliente):
    r = cliente.post("/api/consultas/analitica", headers=cabecera("DECOR_TOKEN_COMERCIAL"), json={
        "sql": "SELECT vkbur, count(DISTINCT vbeln) AS facturas FROM zventas "
               "WHERE erdat BETWEEN '20260901' AND '20260930' GROUP BY vkbur"})
    assert r.status_code == 200
    assert r.json()["total_filas"] > 0


def test_403_escritura(cliente):
    r = cliente.post("/api/consultas/detalle", headers=cabecera("DECOR_TOKEN_COMERCIAL"),
                     json={"sql": "DELETE FROM zventas"})
    assert r.status_code == 403 and r.json()["error"] == "CONSULTA_NO_PERMITIDA"


def test_403_tabla_con_datos_personales_para_comercial(cliente):
    assert cliente.get("/api/tablas/mv_clientes", headers=cabecera("DECOR_TOKEN_COMERCIAL")).status_code == 403


def test_404_consulta_predefinida_inexistente(cliente):
    r = cliente.post("/api/contingencia/consultas/no-existe", headers=cabecera("DECOR_TOKEN_COMERCIAL"), json={})
    assert r.status_code == 404


def test_auditoria_solo_admin(cliente):
    assert cliente.get("/api/auditoria", headers=cabecera("DECOR_TOKEN_COMERCIAL")).status_code == 403
    r = cliente.get("/api/auditoria?limite=5", headers=cabecera("DECOR_TOKEN_ADMIN"))
    assert r.status_code == 200 and len(r.json()) > 0


def test_mcp_tools_list_y_tools_call(cliente):
    cabeceras = {**cabecera("DECOR_TOKEN_COMERCIAL"), "Accept": "application/json, text/event-stream"}
    lista = cliente.post("/mcp", headers=cabeceras, json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"}).json()
    nombres = {t["name"] for t in lista["result"]["tools"]}
    assert nombres == {"business_guide", "list_tables", "describe_table", "sample_rows",
                       "count_rows", "list_distinct", "query_table", "query_analytics"}

    llamada = cliente.post("/mcp", headers=cabeceras, json={
        "jsonrpc": "2.0", "id": 2, "method": "tools/call",
        "params": {"name": "count_rows", "arguments": {"table": "zventas"}}}).json()
    assert llamada["result"]["isError"] is False
    assert json.loads(llamada["result"]["content"][0]["text"])["total"] > 0

    denegada = cliente.post("/mcp", headers=cabeceras, json={
        "jsonrpc": "2.0", "id": 3, "method": "tools/call",
        "params": {"name": "query_table", "arguments": {"sql": "DROP TABLE zventas"}}}).json()
    assert denegada["result"]["isError"] is True
