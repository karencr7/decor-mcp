"""Mapa del negocio que entrega la herramienta business_guide (sección 9 de la
propuesta): qué tabla responde cada tipo de pregunta, las claves de unión y
las reglas que la IA debe respetar."""

REGLAS_NEGOCIO = [
    "Una oferta (mv_zofertas) o un pedido (mv_zpedidos) NO es una venta: lo facturado está SOLO en zventas.",
    "En zventas, netwr es TEXTO y los negativos traen el signo al final (ej. '2765.14-'). "
    "Para sumar usa: CASE WHEN netwr LIKE '%-' THEN -1 * rtrim(netwr,'-')::numeric ELSE netwr::numeric END.",
    "En zventas, erdat es TEXTO con formato AAAAMMDD (ej. '20260930'). Filtra con BETWEEN '20260901' AND '20260930'.",
    "Las existencias de Decorcerámica (zexistencias_cm) y Novacasa (zexistencias_nv) NO se suman entre sí.",
    "Filtra siempre por fecha (y por oficina vkbur cuando aplique) para no recorrer tablas completas.",
    "Prefiere consultas agregadas (query_analytics) y evita traer columnas de datos personales si no son necesarias.",
]

CLAVES_UNION = {
    "vbeln + posnr": "Documento comercial SAP y su posición (ofertas, pedidos, entregas, facturas)",
    "kunnr / kunag / account": "Cliente en SAP / cliente en movilidad",
    "matnr": "Material (producto)",
    "vkbur": "Oficina de ventas (BOG1, MED1, CAL1, BAQ1)",
    "membership_id": "Membresía DecorClub (1 a N movimientos)",
    "zeentregas.vgbel -> mv_zpedidos.vbeln": "Entrega -> pedido de origen",
    "zventas.vgpos -> zeentregas.vbeln": "Factura -> entrega de origen",
}

PREGUNTAS_FRECUENTES = {
    "¿Cuánto se facturó?": "zventas",
    "¿Qué pedidos están abiertos?": "mv_zpedidos (gbstk = 'A')",
    "¿Cuánta cartera está vencida?": "zfi_job_cartera (tot_vencida)",
    "¿Hay existencias de un producto?": "zexistencias_cm / zexistencias_nv",
    "¿Cuántas PQR hay abiertas?": "mv_smarpqr (pqr_status)",
    "¿Cuántos puntos tiene un socio?": "decorclub_membresia",
    "¿Qué tan actualizados están los datos?": "dv_meta (ultima_carga)",
}
