"""Modo de contingencia (sección 10, Tabla 12 nivel 2 y Tabla 13 de la propuesta).

Si el proveedor de IA no está disponible, el Funcionario elige una consulta
predefinida, llena sus parámetros y el sistema la ejecuta directamente, SIN
IA y SIN escribir SQL. Las plantillas son SQL parametrizado revisado por TI y
pasan por la misma Política de acceso que las consultas de la IA.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from app.aplicacion.ejecutar_consulta import EjecutarConsulta
from app.dominio.errores import ParametroInvalido, RecursoNoEncontrado
from app.dominio.modelos import Usuario

_NETWR_NUMERICO = "CASE WHEN netwr LIKE '%%-' THEN -1 * rtrim(netwr, '-')::numeric ELSE netwr::numeric END"


@dataclass(frozen=True)
class Parametro:
    nombre: str
    descripcion: str
    patron: str
    ejemplo: str


@dataclass(frozen=True)
class ConsultaPredefinida:
    id: str
    titulo: str
    tabla: str
    sql: str
    parametros: tuple[Parametro, ...]


_OFICINA = Parametro("oficina", "Oficina de ventas", r"^(BOG1|MED1|CAL1|BAQ1)$", "BOG1")
_MES = Parametro("mes", "Mes en formato AAAAMM", r"^20\d{2}(0[1-9]|1[0-2])$", "202609")
_FECHA = r"^20\d{2}-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])$"

CATALOGO: dict[str, ConsultaPredefinida] = {c.id: c for c in [
    ConsultaPredefinida(
        "facturacion-oficina-mes", "Facturación por oficina y mes", "zventas",
        f"""SELECT vkbur AS oficina,
                   count(DISTINCT vbeln) AS facturas,
                   round(sum({_NETWR_NUMERICO}), 2) AS valor_neto
              FROM zventas
             WHERE vkbur = %(oficina)s
               AND erdat BETWEEN %(mes)s || '01' AND %(mes)s || '31'
             GROUP BY vkbur""",
        (_OFICINA, _MES)),
    ConsultaPredefinida(
        "cartera-vencida-cliente", "Cartera vencida por cliente", "zfi_job_cartera",
        """SELECT kunnr AS cliente, count(*) AS facturas,
                  sum(dmbtr) AS saldo, sum(tot_vencida) AS vencido
             FROM zfi_job_cartera
            WHERE kunnr = %(cliente)s AND zfven <= %(fecha_corte)s::date
            GROUP BY kunnr""",
        (Parametro("cliente", "Cliente SAP (kunnr)", r"^CLI\d{4}$", "CLI2005"),
         Parametro("fecha_corte", "Fecha de corte AAAA-MM-DD", _FECHA, "2026-10-31"))),
    ConsultaPredefinida(
        "existencias-material", "Existencias disponibles por material y canal", "zexistencias_cm / zexistencias_nv",
        """SELECT 'CM' AS canal, matnr, maktx, lot_disp, ord_comp FROM zexistencias_cm
            WHERE matnr = %(material)s AND %(canal)s IN ('CM', 'TODOS')
           UNION ALL
           SELECT 'NV' AS canal, matnr, maktx, lot_disp, ord_comp FROM zexistencias_nv
            WHERE matnr = %(material)s AND %(canal)s IN ('NV', 'TODOS')""",
        (Parametro("material", "Código de material (matnr)", r"^MAT\d{6}$", "MAT100001"),
         Parametro("canal", "CM, NV o TODOS (los canales no se suman)", r"^(CM|NV|TODOS)$", "TODOS"))),
    ConsultaPredefinida(
        "pedidos-estado", "Pedidos por estado", "mv_zpedidos",
        """SELECT gbstk AS estado, count(DISTINCT vbeln) AS pedidos, sum(netwr) AS valor
             FROM mv_zpedidos
            WHERE vkbur = %(oficina)s AND erdat BETWEEN %(desde)s::date AND %(hasta)s::date
            GROUP BY gbstk ORDER BY gbstk""",
        (_OFICINA,
         Parametro("desde", "Fecha inicial AAAA-MM-DD", _FECHA, "2026-09-01"),
         Parametro("hasta", "Fecha final AAAA-MM-DD", _FECHA, "2026-09-30"))),
    ConsultaPredefinida(
        "pqr-oficina", "PQR por oficina y estado", "mv_smarpqr",
        """SELECT c.sales_office AS oficina, p.pqr_status AS estado, count(*) AS pqr
             FROM mv_smarpqr p JOIN mv_clientes c ON c.id_number_fiscal = p.client_document
            WHERE c.sales_office = %(oficina)s AND p.pqr_status = %(estado)s
            GROUP BY c.sales_office, p.pqr_status""",
        (_OFICINA, Parametro("estado", "ABIERTA, EN_PROCESO o CERRADA", r"^(ABIERTA|EN_PROCESO|CERRADA)$", "ABIERTA"))),
    ConsultaPredefinida(
        "puntos-decorclub", "Puntos DecorClub de un socio", "decorclub_membresia",
        """SELECT membership_id, loyalty_level_name AS nivel, points_redeemable_g001 AS puntos
             FROM decorclub_membresia WHERE id_number_fiscal = %(documento)s""",
        (Parametro("documento", "Documento del socio", r"^\d{6,12}$", "912345678"),)),
]}


class ModoContingencia:
    def __init__(self, caso_uso: EjecutarConsulta):
        self._caso_uso = caso_uso

    @staticmethod
    def listar() -> list[dict[str, Any]]:
        return [{"id": c.id, "titulo": c.titulo, "tabla": c.tabla,
                 "parametros": [{"nombre": p.nombre, "descripcion": p.descripcion, "ejemplo": p.ejemplo}
                                for p in c.parametros]}
                for c in CATALOGO.values()]

    def ejecutar(self, usuario: Usuario, consulta_id: str, valores: dict[str, Any]) -> dict[str, Any]:
        consulta = CATALOGO.get(consulta_id)
        if consulta is None:
            raise RecursoNoEncontrado(f"No existe la consulta predefinida '{consulta_id}'.")
        parametros: dict[str, str] = {}
        for p in consulta.parametros:
            valor = str(valores.get(p.nombre, "")).strip()
            if not re.match(p.patron, valor):
                raise ParametroInvalido(f"Parámetro '{p.nombre}' inválido. {p.descripcion}. Ejemplo: {p.ejemplo}")
            parametros[p.nombre] = valor
        resultado = self._caso_uso.ejecutar_plantilla(usuario, consulta.id, consulta.sql, parametros)
        return {"consulta": consulta.id, "titulo": consulta.titulo, "parametros": parametros, **resultado}
