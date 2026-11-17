"""Caso de uso «Ejecutar consulta» (Tabla 3 y Tabla 4 de la propuesta).

Orquesta cada consulta: aplica la Política de acceso (paso 5), pide los datos
al Repositorio (paso 6) y registra la operación en la Auditoría (paso 7).

Los dos adaptadores de entrada (servidor MCP y API REST) y el modo de
contingencia llaman a ESTE mismo caso de uso, así que las reglas se aplican
siempre igual, sin importar por dónde llegue la solicitud.
"""

from __future__ import annotations

import json
import re
import time
from typing import Any, Callable

from app.aplicacion.puertos import RegistroAuditoria, RepositorioDatos
from app.dominio import guia_negocio
from app.dominio.errores import ErrorDecor, ParametroInvalido, RecursoNoEncontrado
from app.dominio.modelos import Canal, EntradaAuditoria, ResultadoConsulta, Tabla, TipoConsulta, Usuario
from app.dominio.politica_acceso import PoliticaAcceso

_MAX_DETALLE_AUDITORIA = 2000
_MAX_LARGO_SQL = 10_000  # caracteres; evita analizar textos enormes con sqlglot


class EjecutarConsulta:
    def __init__(self, repositorio: RepositorioDatos, auditoria: RegistroAuditoria, politica: PoliticaAcceso):
        self._repo = repositorio
        self._auditoria = auditoria
        self._politica = politica

    # ================================================================ herramientas
    def guia_negocio(self, usuario: Usuario, canal: Canal, tabla: str | None = None) -> dict[str, Any]:
        """business_guide: mapa del negocio y catálogo vivo de tablas del usuario."""

        def operacion():
            if tabla:
                return self.describir_tabla_sin_auditar(usuario, tabla), [tabla]
            catalogo = self._catalogo_usuario(usuario)
            return {
                "usuario": {"correo": usuario.correo, "nombre": usuario.nombre,
                            "area": usuario.area, "es_admin": usuario.es_admin},
                "reglas_de_negocio": guia_negocio.REGLAS_NEGOCIO,
                "claves_de_union": guia_negocio.CLAVES_UNION,
                "preguntas_frecuentes": guia_negocio.PREGUNTAS_FRECUENTES,
                "tablas_permitidas": {t.nombre: t.descripcion for t in catalogo},
                "limites": {
                    "query_table": f"{PoliticaAcceso.LIMITE_DETALLE} filas",
                    "query_analytics": f"{PoliticaAcceso.LIMITE_ANALITICA} filas y {PoliticaAcceso.TIEMPO_ANALITICA_S} s",
                    "sample_rows": f"1 a {PoliticaAcceso.MAX_MUESTRA} filas",
                    "list_distinct": f"{PoliticaAcceso.MAX_DISTINTOS} valores",
                },
                "ultima_carga_datos": self._ultima_carga_iso(),
            }, []

        return self._auditar(usuario, canal, "business_guide", {"table": tabla}, operacion)

    def listar_tablas(self, usuario: Usuario, canal: Canal) -> dict[str, Any]:
        """list_tables: tablas permitidas y sus columnas comentadas."""

        def operacion():
            tablas = [self._tabla_a_dict(t) for t in self._catalogo_usuario(usuario)]
            return {"total": len(tablas), "tablas": tablas}, []

        return self._auditar(usuario, canal, "list_tables", {}, operacion)

    def describir_tabla(self, usuario: Usuario, canal: Canal, tabla: str) -> dict[str, Any]:
        """describe_table: columnas y descripciones de una tabla."""
        return self._auditar(usuario, canal, "describe_table", {"table": tabla},
                             lambda: (self.describir_tabla_sin_auditar(usuario, tabla), [tabla]))

    def muestra_filas(self, usuario: Usuario, canal: Canal, tabla: str, limite: int = 10) -> dict[str, Any]:
        """sample_rows: filas reales de una tabla (1 a 50)."""

        def operacion():
            t = self._tabla_autorizada(usuario, tabla)
            n = self._politica.validar_limite_muestra(limite)
            resultado = self._repo.ejecutar(f'SELECT * FROM public."{t.nombre}"', None, n, PoliticaAcceso.TIEMPO_ANALITICA_S)
            return resultado, [t.nombre]

        return self._auditar(usuario, canal, "sample_rows", {"table": tabla, "limit": limite}, operacion)

    def contar_filas(self, usuario: Usuario, canal: Canal, tabla: str,
                     columna: str | None = None, valor: str | None = None) -> dict[str, Any]:
        """count_rows: conteo rápido con filtro de igualdad opcional."""

        def operacion():
            t = self._tabla_autorizada(usuario, tabla)
            if columna:
                c = self._columna(t, columna)
                if valor is None:
                    raise ParametroInvalido("Si envías 'column' también debes enviar 'value'.")
                sql = f'SELECT count(*) AS total FROM public."{t.nombre}" WHERE "{c}"::text = %s'
                parametros = [str(valor)]
            else:
                if valor is not None:
                    raise ParametroInvalido("Si envías 'value' también debes enviar 'column'.")
                sql = f'SELECT count(*) AS total FROM public."{t.nombre}"'
                parametros = None
            resultado = self._repo.ejecutar(sql, parametros, 1, PoliticaAcceso.TIEMPO_ANALITICA_S)
            return {"tabla": t.nombre, "filtro": {columna: valor} if columna else None,
                    "total": resultado.filas[0]["total"]}, [t.nombre]

        return self._auditar(usuario, canal, "count_rows", {"table": tabla, "column": columna, "value": valor}, operacion)

    def valores_distintos(self, usuario: Usuario, canal: Canal, tabla: str, columna: str) -> dict[str, Any]:
        """list_distinct: valores distintos de una columna y su frecuencia (máx. 200)."""

        def operacion():
            t = self._tabla_autorizada(usuario, tabla)
            c = self._columna(t, columna)
            sql = (f'SELECT "{c}" AS valor, count(*) AS frecuencia FROM public."{t.nombre}" '
                   f'GROUP BY "{c}" ORDER BY frecuencia DESC, valor')
            resultado = self._repo.ejecutar(sql, None, PoliticaAcceso.MAX_DISTINTOS, PoliticaAcceso.TIEMPO_ANALITICA_S)
            return resultado, [t.nombre]

        return self._auditar(usuario, canal, "list_distinct", {"table": tabla, "column": columna}, operacion)

    def consultar_sql(self, usuario: Usuario, canal: Canal, sql: str, tipo: TipoConsulta) -> dict[str, Any]:
        """query_table (detalle, 2.000 filas) y query_analytics (agregados, 500 filas, 15 s)."""

        def operacion():
            if len(sql) > _MAX_LARGO_SQL:
                raise ParametroInvalido(f"La consulta supera {_MAX_LARGO_SQL} caracteres.")
            validado = self._politica.validar_sql(usuario, sql)
            limites = self._politica.limites(tipo)
            resultado = self._repo.ejecutar(validado.sql, None, limites.max_filas, limites.tiempo_maximo_s)
            return resultado, list(validado.tablas)

        return self._auditar(usuario, canal, tipo.value, {"sql": sql}, operacion)

    # ================================================================ auxiliares públicos
    def describir_tabla_sin_auditar(self, usuario: Usuario, tabla: str) -> dict[str, Any]:
        return self._tabla_a_dict(self._tabla_autorizada(usuario, tabla))

    def ejecutar_plantilla(self, usuario: Usuario, consulta_id: str, sql: str,
                           parametros: dict[str, Any]) -> dict[str, Any]:
        """Usado por el modo de contingencia: SQL parametrizado y revisado por TI que
        igualmente pasa por la Política de acceso (tablas del usuario, solo lectura)."""

        def operacion():
            # La política analiza el SQL con los marcadores %(nombre)s reemplazados
            # por NULL; a la base se envía la plantilla original con sus parámetros.
            sql_analizable = re.sub(r"%\(\w+\)s", "NULL", sql).replace("%%", "%")
            validado = self._politica.validar_sql(usuario, sql_analizable)
            limites = self._politica.limites(TipoConsulta.ANALITICA)
            resultado = self._repo.ejecutar(sql, parametros, limites.max_filas, limites.tiempo_maximo_s)
            datos = resultado.como_dict()
            datos["ultima_carga_datos"] = self._ultima_carga_iso()
            return datos, list(validado.tablas)

        return self._auditar(usuario, Canal.CONTINGENCIA, f"predefinida:{consulta_id}", parametros, operacion)

    # ================================================================ privados
    def _catalogo_usuario(self, usuario: Usuario) -> list[Tabla]:
        catalogo = self._repo.catalogo()
        return [catalogo[n] for n in sorted(usuario.tablas_autorizadas) if n in catalogo]

    def _tabla_autorizada(self, usuario: Usuario, tabla: str) -> Tabla:
        nombre = self._politica.validar_tabla(usuario, tabla)
        t = self._repo.catalogo().get(nombre)
        if t is None:
            raise RecursoNoEncontrado(f"La tabla '{nombre}' no existe en la base de datos.")
        return t

    def _columna(self, tabla: Tabla, columna: str) -> str:
        nombre = self._politica.normalizar_identificador(columna, "columna")
        if not tabla.tiene_columna(nombre):
            raise ParametroInvalido(f"La columna '{nombre}' no existe en '{tabla.nombre}'. Usa describe_table.")
        return nombre

    @staticmethod
    def _tabla_a_dict(t: Tabla) -> dict[str, Any]:
        return {"tabla": t.nombre, "descripcion": t.descripcion,
                "columnas": [{"nombre": c.nombre, "tipo": c.tipo, "descripcion": c.descripcion} for c in t.columnas]}

    def _ultima_carga_iso(self) -> str | None:
        fecha = self._repo.ultima_carga()
        return fecha.isoformat() if fecha else None

    def _auditar(self, usuario: Usuario, canal: Canal, herramienta: str, argumentos: dict[str, Any],
                 operacion: Callable[[], tuple[Any, list[str]]]) -> dict[str, Any]:
        """Ejecuta la operación y SIEMPRE deja rastro en la auditoría, incluso si se deniega."""
        inicio = time.perf_counter()
        detalle = json.dumps({k: v for k, v in argumentos.items() if v is not None}, ensure_ascii=False, default=str)
        detalle = detalle[:_MAX_DETALLE_AUDITORIA]
        try:
            resultado, tablas = operacion()
        except ErrorDecor as error:
            estado = "DENEGADA" if error.codigo in ("CONSULTA_NO_PERMITIDA", "TABLA_NO_AUTORIZADA") else "ERROR"
            self._auditoria.registrar(EntradaAuditoria(
                correo=usuario.correo, canal=canal, herramienta=herramienta, resultado=estado,
                detalle=detalle, motivo=error.mensaje[:500], duracion_ms=self._ms(inicio)))
            raise
        datos = resultado.como_dict() if isinstance(resultado, ResultadoConsulta) else resultado
        filas = datos.get("total_filas") if isinstance(datos, dict) else None
        self._auditoria.registrar(EntradaAuditoria(
            correo=usuario.correo, canal=canal, herramienta=herramienta, resultado="OK",
            detalle=detalle, tablas=[t.lower() for t in tablas], filas=filas, duracion_ms=self._ms(inicio)))
        return datos

    @staticmethod
    def _ms(inicio: float) -> int:
        return int((time.perf_counter() - inicio) * 1000)
