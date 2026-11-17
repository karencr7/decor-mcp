"""Pruebas de las mejoras de la revisión de código con IA (Módulo 6 · Sesión 2).
Reutilizan los dobles de test_caso_uso.py: sin base de datos."""

import pytest

from app.dominio.errores import ConsultaNoPermitida, ParametroInvalido
from app.dominio.modelos import Canal, TipoConsulta
from tests.test_caso_uso import USUARIO, entorno  # noqa: F401  (entorno es un fixture)


def test_count_rows_con_value_sin_column_es_rechazado(entorno):
    caso_uso, repo, auditoria = entorno
    with pytest.raises(ParametroInvalido, match="column"):
        caso_uso.contar_filas(USUARIO, Canal.REST, "zventas", None, "BOG1")
    assert repo.ejecuciones == []
    assert auditoria.entradas[-1].resultado == "ERROR"


def test_sql_demasiado_largo_se_rechaza_sin_llegar_a_la_base(entorno):
    caso_uso, repo, auditoria = entorno
    sql = "SELECT vbeln FROM zventas WHERE vbeln IN (" + ", ".join(["'F0001'"] * 2000) + ")"
    with pytest.raises(ParametroInvalido, match="caracteres"):
        caso_uso.consultar_sql(USUARIO, Canal.MCP, sql, TipoConsulta.DETALLE)
    assert repo.ejecuciones == []
    assert auditoria.entradas[-1].resultado == "ERROR"


def test_sql_en_el_limite_sigue_permitido(entorno):
    caso_uso, repo, _ = entorno
    base = "SELECT vbeln FROM zventas"
    sql = base + " " * (10_000 - len(base))
    caso_uso.consultar_sql(USUARIO, Canal.MCP, sql, TipoConsulta.DETALLE)
    assert len(repo.ejecuciones) == 1


def test_codigos_de_politica_se_auditan_como_denegada(entorno):
    caso_uso, _, auditoria = entorno
    with pytest.raises(ConsultaNoPermitida):
        caso_uso.consultar_sql(USUARIO, Canal.REST, "UPDATE zventas SET vkbur = 'X'", TipoConsulta.DETALLE)
    assert auditoria.entradas[-1].resultado == "DENEGADA"
