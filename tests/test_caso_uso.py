"""Pruebas del caso de uso «Ejecutar consulta» con adaptadores SIMULADOS.

Demuestra la ventaja de la arquitectura hexagonal (Tabla 5 de la propuesta):
el núcleo se prueba sin base de datos, reemplazando los puertos por dobles.
"""

from datetime import datetime, timezone

import pytest

from app.aplicacion.consultas_predefinidas import ModoContingencia
from app.aplicacion.ejecutar_consulta import EjecutarConsulta
from app.aplicacion.puertos import RegistroAuditoria, RepositorioDatos
from app.dominio.errores import ConsultaNoPermitida, ParametroInvalido, TablaNoAutorizada
from app.dominio.modelos import Canal, Columna, ResultadoConsulta, Tabla, TipoConsulta, Usuario
from app.dominio.politica_acceso import PoliticaAcceso


class RepositorioFalso(RepositorioDatos):
    def __init__(self):
        self.ejecuciones = []

    def catalogo(self):
        return {
            "zventas": Tabla("zventas", "Facturas", (Columna("vbeln", "text"), Columna("vkbur", "text"))),
            "mv_clientes": Tabla("mv_clientes", "Clientes", (Columna("account", "text"),)),
        }

    def ejecutar(self, sql, parametros, max_filas, tiempo_maximo_s):
        self.ejecuciones.append((sql, parametros, max_filas, tiempo_maximo_s))
        return ResultadoConsulta(columnas=["total"], filas=[{"total": 3}], limite_aplicado=max_filas)

    def ultima_carga(self):
        return datetime(2026, 10, 31, tzinfo=timezone.utc)


class AuditoriaEnMemoria(RegistroAuditoria):
    def __init__(self):
        self.entradas = []

    def registrar(self, entrada):
        self.entradas.append(entrada)

    def ultimas(self, limite):
        return self.entradas[-limite:]


@pytest.fixture
def entorno():
    repo, auditoria = RepositorioFalso(), AuditoriaEnMemoria()
    return EjecutarConsulta(repo, auditoria, PoliticaAcceso()), repo, auditoria


USUARIO = Usuario("comercial@demo", "Comercial", "Comercial", False, frozenset({"zventas"}))


def test_query_analytics_aplica_limite_y_tiempo_y_audita(entorno):
    caso_uso, repo, auditoria = entorno
    caso_uso.consultar_sql(USUARIO, Canal.MCP, "SELECT count(*) AS total FROM zventas", TipoConsulta.ANALITICA)
    _, _, max_filas, tiempo = repo.ejecuciones[0]
    assert (max_filas, tiempo) == (500, 15)
    entrada = auditoria.entradas[-1]
    assert (entrada.resultado, entrada.herramienta, entrada.canal, entrada.tablas) == \
           ("OK", "query_analytics", Canal.MCP, ["zventas"])


def test_query_table_permite_2000_filas(entorno):
    caso_uso, repo, _ = entorno
    caso_uso.consultar_sql(USUARIO, Canal.REST, "SELECT * FROM zventas", TipoConsulta.DETALLE)
    assert repo.ejecuciones[0][2] == 2000


def test_consulta_denegada_no_llega_a_la_base_pero_queda_auditada(entorno):
    caso_uso, repo, auditoria = entorno
    with pytest.raises(ConsultaNoPermitida):
        caso_uso.consultar_sql(USUARIO, Canal.MCP, "DELETE FROM zventas", TipoConsulta.DETALLE)
    assert repo.ejecuciones == []
    assert auditoria.entradas[-1].resultado == "DENEGADA"


def test_tabla_no_autorizada_queda_auditada(entorno):
    caso_uso, repo, auditoria = entorno
    with pytest.raises(TablaNoAutorizada):
        caso_uso.describir_tabla(USUARIO, Canal.REST, "mv_clientes")
    assert auditoria.entradas[-1].resultado == "DENEGADA"


def test_count_rows_usa_parametros_y_no_concatena_el_valor(entorno):
    caso_uso, repo, _ = entorno
    resultado = caso_uso.contar_filas(USUARIO, Canal.MCP, "zventas", "vkbur", "BOG1'; DROP TABLE x; --")
    sql, parametros, _, _ = repo.ejecuciones[0]
    assert "DROP" not in sql and parametros == ["BOG1'; DROP TABLE x; --"]
    assert resultado["total"] == 3


def test_columna_inexistente(entorno):
    caso_uso, _, _ = entorno
    with pytest.raises(ParametroInvalido):
        caso_uso.valores_distintos(USUARIO, Canal.MCP, "zventas", "no_existe")


def test_guia_solo_muestra_tablas_del_usuario(entorno):
    caso_uso, _, _ = entorno
    guia = caso_uso.guia_negocio(USUARIO, Canal.MCP)
    assert list(guia["tablas_permitidas"]) == ["zventas"]
    assert guia["usuario"]["correo"] == "comercial@demo"


def test_contingencia_valida_parametros_y_usa_la_politica(entorno):
    caso_uso, repo, auditoria = entorno
    contingencia = ModoContingencia(caso_uso)
    with pytest.raises(ParametroInvalido):
        contingencia.ejecutar(USUARIO, "facturacion-oficina-mes", {"oficina": "XYZ", "mes": "202609"})
    resultado = contingencia.ejecutar(USUARIO, "facturacion-oficina-mes", {"oficina": "BOG1", "mes": "202609"})
    assert resultado["ultima_carga_datos"].startswith("2026-10-31")
    assert repo.ejecuciones[-1][1] == {"oficina": "BOG1", "mes": "202609"}
    assert auditoria.entradas[-1].canal is Canal.CONTINGENCIA
    with pytest.raises(TablaNoAutorizada):  # el comercial no tiene zfi_job_cartera
        contingencia.ejecutar(USUARIO, "cartera-vencida-cliente", {"cliente": "CLI2001", "fecha_corte": "2026-10-31"})
