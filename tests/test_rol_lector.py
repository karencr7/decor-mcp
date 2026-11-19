"""Issue #9: el rol decor_lector (el que usan las herramientas) no puede escribir ni cambiar
el esquema. Se prueba contra PostgreSQL real: es la segunda capa de seguridad, que protege
aunque la Política de acceso fallara. Sin base de datos, estas pruebas se omiten."""

import os

import pytest

psycopg = pytest.importorskip("psycopg")
pytestmark = pytest.mark.skipif(not os.getenv("DECOR_DB_LECTOR_URL"),
                                reason="Requiere PostgreSQL con los datos de demostración")

SENTENCIAS_PROHIBIDAS = [
    "INSERT INTO zventas (vbeln) VALUES ('PRUEBA')",
    "UPDATE zventas SET vkbur = 'XXX1'",
    "DELETE FROM zventas",
    "TRUNCATE zventas",
    "DROP TABLE zventas",
    "ALTER TABLE zventas ADD COLUMN prueba text",
    "CREATE TABLE prueba_escritura (id int)",
    "SELECT * FROM mcp.usuarios",
]


@pytest.mark.parametrize("sql", SENTENCIAS_PROHIBIDAS)
def test_rol_lector_rechaza_escrituras_ddl_y_esquema_interno(sql):
    with psycopg.connect(os.environ["DECOR_DB_LECTOR_URL"]) as conexion:
        with pytest.raises(psycopg.Error):
            conexion.execute(sql)


def test_rol_lector_si_puede_leer_las_tablas_de_negocio():
    with psycopg.connect(os.environ["DECOR_DB_LECTOR_URL"]) as conexion:
        assert conexion.execute("SELECT count(*) FROM zventas").fetchone()[0] > 0
