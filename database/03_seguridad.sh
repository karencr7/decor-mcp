#!/bin/sh
# =====================================================================
# Decor MCP · Roles, permisos y usuarios de demostración.
# Lo ejecuta automáticamente el contenedor de PostgreSQL la PRIMERA vez
# que crea la base. Las contraseñas y tokens llegan como variables de
# entorno desde el archivo .env (que NO se sube a GitHub).
#
# Dos roles de base de datos (defensa en profundidad):
#   decor_lector -> SOLO SELECT sobre las tablas de negocio. Lo usan las
#                   herramientas de consulta. Aunque la política del
#                   servidor fallara, la base rechaza cualquier escritura.
#   decor_app    -> lee usuarios/permisos y ESCRIBE auditoría (esquema mcp).
#                   No puede leer las tablas de negocio.
# =====================================================================
set -e

psql -v ON_ERROR_STOP=1 \
     --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
     -v lector_pass="$DECOR_DB_LECTOR_PASSWORD" \
     -v app_pass="$DECOR_DB_APP_PASSWORD" \
     -v token_admin="$DECOR_TOKEN_ADMIN" \
     -v token_comercial="$DECOR_TOKEN_COMERCIAL" \
     -v token_cartera="$DECOR_TOKEN_CARTERA" <<-'EOSQL'

    -- Roles de conexión -------------------------------------------------
    CREATE ROLE decor_lector LOGIN PASSWORD :'lector_pass';
    CREATE ROLE decor_app    LOGIN PASSWORD :'app_pass';

    REVOKE ALL ON SCHEMA public FROM PUBLIC;
    GRANT USAGE ON SCHEMA public TO decor_lector;
    GRANT SELECT ON ALL TABLES IN SCHEMA public TO decor_lector;
    ALTER ROLE decor_lector SET default_transaction_read_only = on;
    ALTER ROLE decor_lector SET statement_timeout = '30s';

    GRANT USAGE ON SCHEMA mcp TO decor_app;
    GRANT SELECT ON mcp.usuarios, mcp.permisos TO decor_app;
    GRANT SELECT, INSERT ON mcp.auditoria TO decor_app;
    GRANT USAGE ON SEQUENCE mcp.auditoria_id_seq TO decor_app;

    -- Usuarios de demostración (ficticios) --------------------------------
    -- Solo se guarda el hash SHA-256 del token.
    INSERT INTO mcp.usuarios (correo, nombre, area, es_admin, token_hash) VALUES
      ('admin@decor-demo.co',     'Administrador TI (demo)', 'TI y Seguridad', TRUE,
         encode(sha256(convert_to(:'token_admin', 'UTF8')), 'hex')),
      ('comercial@decor-demo.co', 'Funcionario Comercial (demo)', 'Comercial', FALSE,
         encode(sha256(convert_to(:'token_comercial', 'UTF8')), 'hex')),
      ('cartera@decor-demo.co',   'Funcionario Cartera (demo)', 'Cartera', FALSE,
         encode(sha256(convert_to(:'token_cartera', 'UTF8')), 'hex'));

    -- Tablas habilitadas por usuario (mcp_permisos) -----------------------
    -- Administrador: todas las tablas de negocio.
    INSERT INTO mcp.permisos (correo, tabla)
    SELECT 'admin@decor-demo.co', table_name
      FROM information_schema.tables
     WHERE table_schema = 'public' AND table_type = 'BASE TABLE';

    -- Comercial: flujo comercial y existencias, SIN tablas de datos personales.
    INSERT INTO mcp.permisos (correo, tabla) VALUES
      ('comercial@decor-demo.co', 'zventas'),
      ('comercial@decor-demo.co', 'mv_zpedidos'),
      ('comercial@decor-demo.co', 'zeentregas'),
      ('comercial@decor-demo.co', 'mm_maestros'),
      ('comercial@decor-demo.co', 'zexistencias_cm'),
      ('comercial@decor-demo.co', 'zexistencias_nv'),
      ('comercial@decor-demo.co', 'dv_meta');

    -- Cartera: cartera y facturas.
    INSERT INTO mcp.permisos (correo, tabla) VALUES
      ('cartera@decor-demo.co', 'zfi_job_cartera'),
      ('cartera@decor-demo.co', 'zventas'),
      ('cartera@decor-demo.co', 'dv_meta');
EOSQL

echo "Decor MCP: roles, permisos y usuarios de demostración creados."
