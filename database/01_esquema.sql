-- =====================================================================
-- Decor MCP · Esquema de base de datos (PostgreSQL 16)
-- Réplica LOCAL con DATOS FICTICIOS de las tablas principales de la
-- base de Grupo Decor en Supabase (Figura 4 de la propuesta del Módulo 2).
--
-- Esquema "public": tablas de negocio (copias de SAP y de movilidad).
--   Casi todas las columnas son TEXT, igual que en la fuente real, y las
--   relaciones son LÓGICAS por claves SAP (vbeln, posnr, kunnr, matnr).
--   La única llave foránea declarada es la de DecorClub.
-- Esquema "mcp": tablas internas del servidor (usuarios, permisos y
--   auditoría). Nunca se exponen a las herramientas de consulta.
-- =====================================================================

-- ---------------------------------------------------------------------
-- Dominio: Clientes
-- ---------------------------------------------------------------------
CREATE TABLE public.mv_clientes (
    account           TEXT PRIMARY KEY,
    id_number_erp     TEXT UNIQUE,
    id_number_fiscal  TEXT,
    full_name         TEXT,
    email             TEXT,
    cellphone         TEXT,
    sales_office      TEXT
);
COMMENT ON TABLE  public.mv_clientes IS 'Clientes del sistema de movilidad. Contiene datos personales (Ley 1581).';
COMMENT ON COLUMN public.mv_clientes.account IS 'Identificador del cliente en movilidad';
COMMENT ON COLUMN public.mv_clientes.id_number_erp IS 'Código del cliente en SAP (une con zcrm_maestro_cliente.cliente_sd y kunnr)';
COMMENT ON COLUMN public.mv_clientes.id_number_fiscal IS 'Documento fiscal (NIT/CC). Dato personal';
COMMENT ON COLUMN public.mv_clientes.full_name IS 'Nombre completo. Dato personal';
COMMENT ON COLUMN public.mv_clientes.email IS 'Correo. Dato personal';
COMMENT ON COLUMN public.mv_clientes.cellphone IS 'Celular. Dato personal';
COMMENT ON COLUMN public.mv_clientes.sales_office IS 'Oficina de ventas asignada (vkbur)';

CREATE TABLE public.zcrm_maestro_cliente (
    id                  BIGINT PRIMARY KEY,
    cliente_sd          TEXT UNIQUE,
    nif                 TEXT,
    nombre_cliente      TEXT,
    correo_electronico  TEXT,
    telefono            TEXT,
    oficina_vta         TEXT
);
COMMENT ON TABLE  public.zcrm_maestro_cliente IS 'Maestro de clientes de SAP CRM. Contiene datos personales (Ley 1581).';
COMMENT ON COLUMN public.zcrm_maestro_cliente.cliente_sd IS 'Código del cliente en SAP (kunnr)';
COMMENT ON COLUMN public.zcrm_maestro_cliente.nif IS 'Documento fiscal. Dato personal';
COMMENT ON COLUMN public.zcrm_maestro_cliente.nombre_cliente IS 'Nombre del cliente. Dato personal';
COMMENT ON COLUMN public.zcrm_maestro_cliente.correo_electronico IS 'Correo. Dato personal';
COMMENT ON COLUMN public.zcrm_maestro_cliente.telefono IS 'Teléfono. Dato personal';
COMMENT ON COLUMN public.zcrm_maestro_cliente.oficina_vta IS 'Oficina de ventas';

-- ---------------------------------------------------------------------
-- Dominio: DecorClub (fidelización)
-- ---------------------------------------------------------------------
CREATE TABLE public.decorclub_membresia (
    membership_id           TEXT PRIMARY KEY,
    account                 TEXT,
    id_number_fiscal        TEXT,
    client_name             TEXT,
    loyalty_level_name      TEXT,
    points_redeemable_g001  NUMERIC(12,2)
);
COMMENT ON TABLE  public.decorclub_membresia IS 'Membresías del programa DecorClub. Contiene datos personales (Ley 1581).';
COMMENT ON COLUMN public.decorclub_membresia.account IS 'Cliente en movilidad (une con mv_clientes.account)';
COMMENT ON COLUMN public.decorclub_membresia.id_number_fiscal IS 'Documento del socio. Dato personal';
COMMENT ON COLUMN public.decorclub_membresia.client_name IS 'Nombre del socio. Dato personal';
COMMENT ON COLUMN public.decorclub_membresia.loyalty_level_name IS 'Nivel del socio (Plata, Oro, Platino)';
COMMENT ON COLUMN public.decorclub_membresia.points_redeemable_g001 IS 'Puntos redimibles';

CREATE TABLE public.decorclub_movimiento (
    id                UUID PRIMARY KEY,
    membership_id     TEXT NOT NULL REFERENCES public.decorclub_membresia (membership_id),
    reference_type    TEXT,
    reference_number  TEXT,
    creation_date     DATE,
    points_total      NUMERIC(12,2)
);
COMMENT ON TABLE  public.decorclub_movimiento IS 'Movimientos de puntos DecorClub (única llave foránea declarada del modelo).';
COMMENT ON COLUMN public.decorclub_movimiento.reference_type IS 'FAC = factura (suma puntos), NC = nota crédito (resta puntos)';
COMMENT ON COLUMN public.decorclub_movimiento.reference_number IS 'Número de factura (une con zventas.vbeln)';
COMMENT ON COLUMN public.decorclub_movimiento.points_total IS 'Puntos del movimiento';

-- ---------------------------------------------------------------------
-- Dominio: Flujo comercial  oferta -> pedido -> entrega -> factura
-- ---------------------------------------------------------------------
CREATE TABLE public.mv_zofertas (
    vbeln             TEXT,
    posnr             TEXT,
    kunnr             TEXT,
    matnr             TEXT,
    id_number_fiscal  TEXT,
    audat             DATE,
    vkbur             TEXT,
    netwr             NUMERIC(14,2),
    PRIMARY KEY (vbeln, posnr)
);
COMMENT ON TABLE  public.mv_zofertas IS 'Ofertas (cotizaciones). Una oferta NO es una venta.';
COMMENT ON COLUMN public.mv_zofertas.vbeln IS 'Número de oferta';
COMMENT ON COLUMN public.mv_zofertas.posnr IS 'Posición';
COMMENT ON COLUMN public.mv_zofertas.kunnr IS 'Cliente SAP';
COMMENT ON COLUMN public.mv_zofertas.matnr IS 'Material';
COMMENT ON COLUMN public.mv_zofertas.id_number_fiscal IS 'Documento del cliente. Dato personal';
COMMENT ON COLUMN public.mv_zofertas.audat IS 'Fecha de la oferta';
COMMENT ON COLUMN public.mv_zofertas.vkbur IS 'Oficina de ventas';
COMMENT ON COLUMN public.mv_zofertas.netwr IS 'Valor neto ofertado (COP)';

CREATE TABLE public.mv_zpedidos (
    vbeln   TEXT,
    posnr   TEXT,
    kunnr   TEXT,
    matnr   TEXT,
    erdat   DATE,
    vkbur   TEXT,
    gbstk   TEXT,
    netwr   NUMERIC(14,2),
    PRIMARY KEY (vbeln, posnr)
);
COMMENT ON TABLE  public.mv_zpedidos IS 'Pedidos de venta. Un pedido NO es una factura.';
COMMENT ON COLUMN public.mv_zpedidos.vbeln IS 'Número de pedido';
COMMENT ON COLUMN public.mv_zpedidos.posnr IS 'Posición';
COMMENT ON COLUMN public.mv_zpedidos.kunnr IS 'Cliente SAP';
COMMENT ON COLUMN public.mv_zpedidos.matnr IS 'Material';
COMMENT ON COLUMN public.mv_zpedidos.erdat IS 'Fecha de creación del pedido';
COMMENT ON COLUMN public.mv_zpedidos.vkbur IS 'Oficina de ventas';
COMMENT ON COLUMN public.mv_zpedidos.gbstk IS 'Estado global: A = abierto, B = parcial, C = completo';
COMMENT ON COLUMN public.mv_zpedidos.netwr IS 'Valor neto del pedido (COP)';

CREATE TABLE public.zeentregas (
    vbeln   TEXT,
    posnr   TEXT,
    vgbel   TEXT,
    kunag   TEXT,
    matnr   TEXT,
    tknum   TEXT,
    erdat   DATE,
    PRIMARY KEY (vbeln, posnr)
);
COMMENT ON TABLE  public.zeentregas IS 'Entregas (despachos) de pedidos.';
COMMENT ON COLUMN public.zeentregas.vbeln IS 'Número de entrega';
COMMENT ON COLUMN public.zeentregas.vgbel IS 'Pedido de origen (une con mv_zpedidos.vbeln)';
COMMENT ON COLUMN public.zeentregas.kunag IS 'Cliente solicitante';
COMMENT ON COLUMN public.zeentregas.tknum IS 'Número de transporte';
COMMENT ON COLUMN public.zeentregas.erdat IS 'Fecha de la entrega';

CREATE TABLE public.zventas (
    vbeln   TEXT,
    posnr   TEXT,
    kunag   TEXT,
    matnr   TEXT,
    vgpos   TEXT,
    vkbur   TEXT,
    erdat   TEXT,
    netwr   TEXT,
    PRIMARY KEY (vbeln, posnr)
);
COMMENT ON TABLE  public.zventas IS 'Facturas (ventas reales). Lo facturado está SOLO aquí.';
COMMENT ON COLUMN public.zventas.vbeln IS 'Número de factura';
COMMENT ON COLUMN public.zventas.posnr IS 'Posición';
COMMENT ON COLUMN public.zventas.kunag IS 'Cliente SAP';
COMMENT ON COLUMN public.zventas.matnr IS 'Material';
COMMENT ON COLUMN public.zventas.vgpos IS 'Entrega de origen (une con zeentregas.vbeln)';
COMMENT ON COLUMN public.zventas.vkbur IS 'Oficina de ventas';
COMMENT ON COLUMN public.zventas.erdat IS 'Fecha de factura como texto AAAAMMDD';
COMMENT ON COLUMN public.zventas.netwr IS 'Valor neto como TEXTO; los negativos traen el signo al final (ej. 2765.14-)';

CREATE TABLE public.zfi_job_cartera (
    id_cons      TEXT PRIMARY KEY,
    kunnr        TEXT,
    vbeln        TEXT,
    dmbtr        NUMERIC(14,2),
    zfven        DATE,
    tot_vencida  NUMERIC(14,2)
);
COMMENT ON TABLE  public.zfi_job_cartera IS 'Cartera (cuentas por cobrar) por factura.';
COMMENT ON COLUMN public.zfi_job_cartera.kunnr IS 'Cliente SAP';
COMMENT ON COLUMN public.zfi_job_cartera.vbeln IS 'Factura (une con zventas.vbeln)';
COMMENT ON COLUMN public.zfi_job_cartera.dmbtr IS 'Saldo pendiente (COP)';
COMMENT ON COLUMN public.zfi_job_cartera.zfven IS 'Fecha de vencimiento';
COMMENT ON COLUMN public.zfi_job_cartera.tot_vencida IS 'Valor vencido a la fecha de corte (COP)';

CREATE TABLE public.mv_smarpqr (
    code             TEXT PRIMARY KEY,
    invoice_code     TEXT,
    material_id      TEXT,
    client_document  TEXT,
    pqr_status       TEXT,
    created_at       TIMESTAMPTZ
);
COMMENT ON TABLE  public.mv_smarpqr IS 'Peticiones, quejas y reclamos (PQR). Contiene datos personales (Ley 1581).';
COMMENT ON COLUMN public.mv_smarpqr.invoice_code IS 'Factura relacionada (une con zventas.vbeln)';
COMMENT ON COLUMN public.mv_smarpqr.material_id IS 'Material reclamado (une con mm_maestros.matnr)';
COMMENT ON COLUMN public.mv_smarpqr.client_document IS 'Documento del cliente. Dato personal';
COMMENT ON COLUMN public.mv_smarpqr.pqr_status IS 'Estado: ABIERTA, EN_PROCESO, CERRADA';
COMMENT ON COLUMN public.mv_smarpqr.created_at IS 'Fecha de radicación';

-- ---------------------------------------------------------------------
-- Dominio: Materiales y existencias
-- ---------------------------------------------------------------------
CREATE TABLE public.mm_maestros (
    matnr  TEXT PRIMARY KEY,
    maktx  TEXT,
    mvgr1  TEXT,
    mvgr3  TEXT,
    peso   TEXT,
    costo  TEXT
);
COMMENT ON TABLE  public.mm_maestros IS 'Maestro de materiales (productos).';
COMMENT ON COLUMN public.mm_maestros.matnr IS 'Código del material';
COMMENT ON COLUMN public.mm_maestros.maktx IS 'Descripción del material';
COMMENT ON COLUMN public.mm_maestros.mvgr1 IS 'Marca';
COMMENT ON COLUMN public.mm_maestros.mvgr3 IS 'Agrupación (línea de producto)';
COMMENT ON COLUMN public.mm_maestros.peso IS 'Peso en kg (texto)';
COMMENT ON COLUMN public.mm_maestros.costo IS 'Costo unitario en COP (texto)';

CREATE TABLE public.zexistencias_cm (
    matnr     TEXT PRIMARY KEY,
    maktx     TEXT,
    lot_disp  NUMERIC(12,2),
    ord_comp  NUMERIC(12,2)
);
COMMENT ON TABLE  public.zexistencias_cm IS 'Existencias del canal Decorcerámica (CM). NO se suman con Novacasa (NV).';
COMMENT ON COLUMN public.zexistencias_cm.lot_disp IS 'Cantidad disponible';
COMMENT ON COLUMN public.zexistencias_cm.ord_comp IS 'Cantidad en órdenes de compra';

CREATE TABLE public.zexistencias_nv (
    matnr     TEXT PRIMARY KEY,
    maktx     TEXT,
    lot_disp  NUMERIC(12,2),
    ord_comp  NUMERIC(12,2)
);
COMMENT ON TABLE  public.zexistencias_nv IS 'Existencias del canal Novacasa (NV). NO se suman con Decorcerámica (CM).';
COMMENT ON COLUMN public.zexistencias_nv.lot_disp IS 'Cantidad disponible';
COMMENT ON COLUMN public.zexistencias_nv.ord_comp IS 'Cantidad en órdenes de compra';

-- ---------------------------------------------------------------------
-- Metadatos de carga (usados por el modo de contingencia)
-- ---------------------------------------------------------------------
CREATE TABLE public.dv_meta (
    tabla           TEXT PRIMARY KEY,
    ultima_carga    TIMESTAMPTZ NOT NULL,
    filas_cargadas  INTEGER NOT NULL
);
COMMENT ON TABLE public.dv_meta IS 'Fecha de la última carga desde SAP por tabla.';

-- =====================================================================
-- Esquema interno del servidor MCP (no consultable por las herramientas)
-- =====================================================================
CREATE SCHEMA mcp;

CREATE TABLE mcp.usuarios (
    correo      TEXT PRIMARY KEY,
    nombre      TEXT NOT NULL,
    area        TEXT NOT NULL,
    es_admin    BOOLEAN NOT NULL DEFAULT FALSE,
    token_hash  TEXT NOT NULL UNIQUE,
    activo      BOOLEAN NOT NULL DEFAULT TRUE
);
COMMENT ON TABLE  mcp.usuarios IS 'Usuarios del asistente. Solo se guarda el hash SHA-256 del token, nunca el token.';

CREATE TABLE mcp.permisos (
    correo  TEXT NOT NULL REFERENCES mcp.usuarios (correo),
    tabla   TEXT NOT NULL,
    PRIMARY KEY (correo, tabla)
);
COMMENT ON TABLE mcp.permisos IS 'Tablas habilitadas por usuario (mcp_permisos del diseño). Agregar una fila habilita una tabla sin redesplegar.';

CREATE TABLE mcp.auditoria (
    id           BIGSERIAL PRIMARY KEY,
    fecha        TIMESTAMPTZ NOT NULL DEFAULT now(),
    correo       TEXT,
    canal        TEXT NOT NULL,
    herramienta  TEXT NOT NULL,
    detalle      TEXT,
    tablas       TEXT,
    resultado    TEXT NOT NULL,
    motivo       TEXT,
    filas        INTEGER,
    duracion_ms  INTEGER
);
COMMENT ON TABLE mcp.auditoria IS 'Registro de auditoría: quién consultó qué, cuándo, por qué canal y con qué resultado.';
CREATE INDEX ix_auditoria_fecha ON mcp.auditoria (fecha DESC);
