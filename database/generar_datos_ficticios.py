"""Genera database/02_datos_ficticios.sql con datos INVENTADOS.

Todos los nombres, documentos, correos y teléfonos son ficticios. No hay
ningún dato real de Grupo Decor ni de sus clientes. La semilla es fija, así
que el resultado es siempre el mismo (reproducible).

Uso:  python database/generar_datos_ficticios.py
"""

import random
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

random.seed(2026)

OFICINAS = ["BOG1", "MED1", "CAL1", "BAQ1"]
NOMBRES = ["Andrea", "Carlos", "Diana", "Felipe", "Gloria", "Héctor", "Isabel", "Jorge",
           "Laura", "Mauricio", "Natalia", "Óscar", "Paula", "Ricardo", "Sandra", "Tomás",
           "Valentina", "Wilson", "Ximena", "Yolanda"]
APELLIDOS = ["Ríos", "Gómez", "Pardo", "Salas", "Mejía", "Torres", "Lozano", "Cárdenas",
             "Duarte", "Quintero", "Arango", "Benítez"]
MARCAS = ["Decorcerámica", "Novacasa", "Corona", "Alfa", "Grival"]
LINEAS = ["Pisos", "Paredes", "Grifería", "Sanitarios", "Muebles de baño", "Adhesivos"]
PRODUCTOS = {
    "Pisos": ["Porcelanato Roma 60x60", "Cerámica Madera Roble 20x120", "Porcelanato Mármol Blanco 80x80"],
    "Paredes": ["Revestimiento Metro Blanco", "Enchape Piedra Gris", "Revestimiento Hexagonal Azul"],
    "Grifería": ["Grifo Lavamanos Monocontrol", "Ducha Teléfono Cromada", "Mezclador Cocina Negro"],
    "Sanitarios": ["Sanitario One Piece Blanco", "Sanitario Ahorrador Dual", "Orinal Ecológico"],
    "Muebles de baño": ["Mueble Flotante 60 cm", "Espejo LED Redondo", "Gabinete Esquinero"],
    "Adhesivos": ["Pegante Porcelanato 25 kg", "Boquilla Epóxica Gris", "Impermeabilizante 4 L"],
}


def q(valor):
    """Convierte un valor de Python en literal SQL."""
    if valor is None:
        return "NULL"
    if isinstance(valor, (int, float)):
        return str(valor)
    texto = str(valor).replace("'", "''")
    return f"'{texto}'"


def insert(tabla, columnas, filas):
    lineas = [f"INSERT INTO public.{tabla} ({', '.join(columnas)}) VALUES"]
    valores = [f"  ({', '.join(q(v) for v in fila)})" for fila in filas]
    return "\n".join(lineas) + "\n" + ",\n".join(valores) + ";\n"


def fecha_aleatoria(inicio: date, fin: date) -> date:
    return inicio + timedelta(days=random.randint(0, (fin - inicio).days))


def main():
    salida = ["-- Datos FICTICIOS generados por database/generar_datos_ficticios.py",
              "-- Ningún dato corresponde a personas o documentos reales.", ""]

    # Materiales ------------------------------------------------------------
    materiales = []
    n = 100001
    for linea, nombres in PRODUCTOS.items():
        for nombre in nombres:
            materiales.append({
                "matnr": f"MAT{n}", "maktx": nombre, "mvgr1": random.choice(MARCAS),
                "mvgr3": linea, "peso": f"{random.uniform(0.5, 30):.2f}",
                "costo": f"{random.randint(15, 900) * 1000}",
            })
            n += 1
    salida.append(insert("mm_maestros", ["matnr", "maktx", "mvgr1", "mvgr3", "peso", "costo"],
                         [[m[k] for k in ("matnr", "maktx", "mvgr1", "mvgr3", "peso", "costo")] for m in materiales]))
    for canal in ("cm", "nv"):
        salida.append(insert(f"zexistencias_{canal}", ["matnr", "maktx", "lot_disp", "ord_comp"],
                             [[m["matnr"], m["maktx"], random.randint(0, 800), random.randint(0, 300)]
                              for m in materiales]))

    # Clientes --------------------------------------------------------------
    clientes = []
    for i in range(1, 25):
        nombre = f"{random.choice(NOMBRES)} {random.choice(APELLIDOS)} {random.choice(APELLIDOS)}"
        clientes.append({
            "account": f"ACC{i:04d}", "kunnr": f"CLI{2000 + i}",
            "doc": f"9{random.randint(10000000, 99999999)}",
            "nombre": nombre,
            "email": f"cliente{i:02d}@ejemplo.com",
            "cel": f"300000{i:04d}",
            "oficina": random.choice(OFICINAS),
        })
    salida.append(insert("mv_clientes",
                         ["account", "id_number_erp", "id_number_fiscal", "full_name", "email", "cellphone", "sales_office"],
                         [[c["account"], c["kunnr"], c["doc"], c["nombre"], c["email"], c["cel"], c["oficina"]] for c in clientes]))
    salida.append(insert("zcrm_maestro_cliente",
                         ["id", "cliente_sd", "nif", "nombre_cliente", "correo_electronico", "telefono", "oficina_vta"],
                         [[i + 1, c["kunnr"], c["doc"], c["nombre"], c["email"], c["cel"], c["oficina"]]
                          for i, c in enumerate(clientes)]))

    # Flujo comercial -------------------------------------------------------
    ofertas, pedidos, entregas, ventas, cartera = [], [], [], [], []
    inicio, fin = date(2026, 6, 1), date(2026, 10, 25)
    num_oferta, num_pedido, num_entrega, num_factura = 20000001, 30000001, 80000001, 90000001
    for _ in range(420):
        c = random.choice(clientes)
        f_oferta = fecha_aleatoria(inicio, fin - timedelta(days=12))
        posiciones = random.sample(materiales, random.randint(1, 3))
        oferta = f"{num_oferta}"
        num_oferta += 1
        lineas_oferta = []
        for p, m in enumerate(posiciones, start=1):
            valor = round(random.randint(2, 40) * int(m["costo"]) * 1.35, 2)
            lineas_oferta.append((f"{p * 10:06d}", m, valor))
            ofertas.append([oferta, f"{p * 10:06d}", c["kunnr"], m["matnr"], c["doc"], f_oferta, c["oficina"], valor])
        if random.random() < 0.3:      # 30 % de las ofertas no se convierten en pedido
            continue
        pedido = f"{num_pedido}"
        num_pedido += 1
        f_pedido = f_oferta + timedelta(days=random.randint(0, 5))
        estado = random.choices(["A", "B", "C"], weights=[2, 1, 6])[0]
        for posnr, m, valor in lineas_oferta:
            pedidos.append([pedido, posnr, c["kunnr"], m["matnr"], f_pedido, c["oficina"], estado, valor])
        if estado == "A":              # pedido abierto: aún sin entrega ni factura
            continue
        entrega = f"{num_entrega}"
        num_entrega += 1
        f_entrega = f_pedido + timedelta(days=random.randint(1, 4))
        factura = f"{num_factura}"
        num_factura += 1
        f_factura = f_entrega + timedelta(days=random.randint(0, 2))
        total_factura = 0.0
        for posnr, m, valor in lineas_oferta:
            entregas.append([entrega, posnr, pedido, c["kunnr"], m["matnr"], f"TR{random.randint(1000, 9999)}", f_entrega])
            ventas.append([factura, posnr, c["kunnr"], m["matnr"], entrega, c["oficina"],
                           f_factura.strftime("%Y%m%d"), f"{valor:.2f}"])
            total_factura += valor
        if random.random() < 0.08:     # algunas devoluciones: valor negativo con signo al final (regla SAP)
            m = random.choice(materiales)
            ventas.append([factura, "000900", c["kunnr"], m["matnr"], entrega, c["oficina"],
                           f_factura.strftime("%Y%m%d"), f"{random.randint(50, 900) * 1000 * 1.0:.2f}-"])
        if random.random() < 0.45:     # facturas con saldo en cartera
            vence = f_factura + timedelta(days=30)
            vencido = round(total_factura * random.uniform(0.2, 1.0), 2) if vence < date(2026, 10, 31) else 0
            cartera.append([f"CR{len(cartera) + 1:05d}", c["kunnr"], factura, round(total_factura, 2), vence, vencido])

    salida.append(insert("mv_zofertas", ["vbeln", "posnr", "kunnr", "matnr", "id_number_fiscal", "audat", "vkbur", "netwr"], ofertas))
    salida.append(insert("mv_zpedidos", ["vbeln", "posnr", "kunnr", "matnr", "erdat", "vkbur", "gbstk", "netwr"], pedidos))
    salida.append(insert("zeentregas", ["vbeln", "posnr", "vgbel", "kunag", "matnr", "tknum", "erdat"], entregas))
    salida.append(insert("zventas", ["vbeln", "posnr", "kunag", "matnr", "vgpos", "vkbur", "erdat", "netwr"], ventas))
    salida.append(insert("zfi_job_cartera", ["id_cons", "kunnr", "vbeln", "dmbtr", "zfven", "tot_vencida"], cartera))

    # DecorClub ------------------------------------------------------------
    socios = random.sample(clientes, 12)
    membresias, movimientos = [], []
    facturas_por_cliente = {}
    for v in ventas:
        facturas_por_cliente.setdefault(v[2], set()).add(v[0])
    for i, c in enumerate(socios, start=1):
        mid = f"DC{i:05d}"
        puntos = 0
        for factura in sorted(facturas_por_cliente.get(c["kunnr"], [])):
            p = random.randint(50, 600)
            puntos += p
            movimientos.append([str(uuid.UUID(int=random.getrandbits(128))), mid, "FAC", factura,
                                fecha_aleatoria(inicio, fin), p])
            if random.random() < 0.15:
                movimientos.append([str(uuid.UUID(int=random.getrandbits(128))), mid, "NC", factura,
                                    fecha_aleatoria(inicio, fin), -min(p, 100)])
                puntos -= min(p, 100)
        nivel = "Platino" if puntos > 1500 else "Oro" if puntos > 600 else "Plata"
        membresias.append([mid, c["account"], c["doc"], c["nombre"], nivel, puntos])
    salida.append(insert("decorclub_membresia",
                         ["membership_id", "account", "id_number_fiscal", "client_name", "loyalty_level_name", "points_redeemable_g001"],
                         membresias))
    if movimientos:
        salida.append(insert("decorclub_movimiento",
                             ["id", "membership_id", "reference_type", "reference_number", "creation_date", "points_total"],
                             movimientos))

    # PQR ------------------------------------------------------------------
    pqr = []
    facturas = sorted({(v[0], v[2], v[3]) for v in ventas})
    docs = {c["kunnr"]: c["doc"] for c in clientes}
    for i, (factura, kunnr, matnr) in enumerate(random.sample(facturas, 18), start=1):
        creada = datetime.combine(fecha_aleatoria(inicio, fin), datetime.min.time(), tzinfo=timezone.utc) + timedelta(hours=random.randint(8, 17))
        pqr.append([f"PQR{i:05d}", factura, matnr, docs[kunnr],
                    random.choices(["ABIERTA", "EN_PROCESO", "CERRADA"], weights=[3, 2, 5])[0], creada.isoformat()])
    salida.append(insert("mv_smarpqr", ["code", "invoice_code", "material_id", "client_document", "pqr_status", "created_at"], pqr))

    # Metadatos de carga ------------------------------------------------------
    carga = "2026-10-31T23:30:00+00:00"
    conteos = {"mm_maestros": len(materiales), "mv_clientes": len(clientes), "mv_zofertas": len(ofertas),
               "mv_zpedidos": len(pedidos), "zeentregas": len(entregas), "zventas": len(ventas),
               "zfi_job_cartera": len(cartera), "decorclub_membresia": len(membresias), "mv_smarpqr": len(pqr)}
    salida.append(insert("dv_meta", ["tabla", "ultima_carga", "filas_cargadas"],
                         [[t, carga, n] for t, n in conteos.items()]))

    destino = Path(__file__).with_name("02_datos_ficticios.sql")
    destino.write_text("\n".join(salida), encoding="utf-8")
    print(f"Generado {destino} ({sum(conteos.values())} filas principales)")


if __name__ == "__main__":
    main()
