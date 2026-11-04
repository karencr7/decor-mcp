"""Pruebas unitarias de la Política de acceso (núcleo, sin base de datos)."""

import pytest

from app.dominio.errores import ConsultaNoPermitida, ParametroInvalido, TablaNoAutorizada
from app.dominio.modelos import TipoConsulta, Usuario
from app.dominio.politica_acceso import PoliticaAcceso

politica = PoliticaAcceso()
COMERCIAL = Usuario("comercial@demo", "Comercial", "Comercial", False, frozenset({"zventas", "mm_maestros"}))


@pytest.mark.parametrize("sql, tablas", [
    ("SELECT vkbur, count(*) FROM zventas GROUP BY vkbur", ("zventas",)),
    ("select * from zventas;", ("zventas",)),
    ("WITH t AS (SELECT * FROM zventas) SELECT * FROM t", ("zventas",)),
    ("SELECT * FROM zventas v JOIN mm_maestros m ON m.matnr = v.matnr WHERE v.netwr LIKE '%-'",
     ("mm_maestros", "zventas")),
    ("SELECT matnr FROM zventas UNION SELECT matnr FROM mm_maestros", ("mm_maestros", "zventas")),
])
def test_acepta_consultas_de_lectura_sobre_tablas_autorizadas(sql, tablas):
    assert politica.validar_sql(COMERCIAL, sql).tablas == tablas


@pytest.mark.parametrize("sql", [
    "DELETE FROM zventas",
    "INSERT INTO zventas (vbeln) VALUES ('1')",
    "UPDATE zventas SET netwr = '0'",
    "TRUNCATE zventas",
    "DROP TABLE zventas",
    "SELECT 1; DROP TABLE zventas",
    "SELECT * INTO copia FROM zventas",
    "WITH x AS (DELETE FROM zventas RETURNING *) SELECT * FROM x",
    "SELECT * FROM zventas FOR UPDATE",
    "SET ROLE postgres",
])
def test_rechaza_escrituras_y_varias_sentencias(sql):
    with pytest.raises(ConsultaNoPermitida):
        politica.validar_sql(COMERCIAL, sql)


@pytest.mark.parametrize("sql", [
    "SELECT * FROM mv_clientes",
    "SELECT * FROM zventas WHERE kunag IN (SELECT id_number_erp FROM mv_clientes)",
    "SELECT * FROM mcp.usuarios",
    "SELECT * FROM pg_catalog.pg_roles",
    "SELECT * FROM information_schema.tables",
])
def test_rechaza_tablas_no_autorizadas_y_otros_esquemas(sql):
    with pytest.raises(TablaNoAutorizada):
        politica.validar_sql(COMERCIAL, sql)


def test_sql_mal_escrito_es_parametro_invalido():
    with pytest.raises(ParametroInvalido):
        politica.validar_sql(COMERCIAL, "SELECT FROM WHERE (")


def test_limites_del_diseno():
    assert politica.limites(TipoConsulta.DETALLE).max_filas == 2000
    analitica = politica.limites(TipoConsulta.ANALITICA)
    assert (analitica.max_filas, analitica.tiempo_maximo_s) == (500, 15)


@pytest.mark.parametrize("limite", [0, 51])
def test_muestra_fuera_de_rango(limite):
    with pytest.raises(ParametroInvalido):
        politica.validar_limite_muestra(limite)


def test_identificadores_peligrosos_se_rechazan():
    with pytest.raises(ParametroInvalido):
        politica.validar_tabla(COMERCIAL, 'zventas"; DROP TABLE x; --')
