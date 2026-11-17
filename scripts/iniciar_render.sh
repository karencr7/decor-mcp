#!/bin/sh
# Arranque de la demo en Render: crea PostgreSQL con los scripts de database/ y luego inicia la API.
# Variables requeridas (Render las genera con render.yaml): POSTGRES_PASSWORD, DECOR_DB_LECTOR_PASSWORD,
# DECOR_DB_APP_PASSWORD, DECOR_TOKEN_ADMIN, DECOR_TOKEN_COMERCIAL, DECOR_TOKEN_CARTERA. Opcional: GROQ_API_KEY.
set -eu

PGBIN=/usr/lib/postgresql/16/bin
export PGDATA="$HOME/pgdata"
export PGHOST=/tmp
export POSTGRES_USER="${POSTGRES_USER:-decor_admin}"
export POSTGRES_DB=decor

echo "Decor MCP: creando la base de datos de demostración..."
rm -rf "$PGDATA"
printf '%s' "$POSTGRES_PASSWORD" > /tmp/pgpass_init
"$PGBIN/initdb" -D "$PGDATA" -U "$POSTGRES_USER" --pwfile=/tmp/pgpass_init \
  --auth-local=trust --auth-host=scram-sha-256 --encoding=UTF8 --locale=C.UTF-8 > /dev/null
rm -f /tmp/pgpass_init
"$PGBIN/pg_ctl" -D "$PGDATA" -l /tmp/postgres.log -w \
  -o "-c listen_addresses=127.0.0.1 -c unix_socket_directories=/tmp" start

psql -v ON_ERROR_STOP=1 -q -U "$POSTGRES_USER" -d postgres -c "CREATE DATABASE decor"
psql -v ON_ERROR_STOP=1 -q -U "$POSTGRES_USER" -d decor -f database/01_esquema.sql > /dev/null
psql -v ON_ERROR_STOP=1 -q -U "$POSTGRES_USER" -d decor -f database/02_datos_ficticios.sql > /dev/null
sh database/03_seguridad.sh

# Las claves que genera Render pueden traer + / = : se codifican para usarlas en la URL de conexión.
codificar() { python -c "import sys, urllib.parse; print(urllib.parse.quote(sys.argv[1], safe=''))" "$1"; }
export DECOR_DB_LECTOR_URL="postgresql://decor_lector:$(codificar "$DECOR_DB_LECTOR_PASSWORD")@127.0.0.1:5432/decor"
export DECOR_DB_APP_URL="postgresql://decor_app:$(codificar "$DECOR_DB_APP_PASSWORD")@127.0.0.1:5432/decor"

# El endpoint MCP solo acepta los hosts conocidos (protección DNS rebinding); Render informa su dominio.
export DECOR_MCP_HOSTS_PERMITIDOS="${DECOR_MCP_HOSTS_PERMITIDOS:-localhost:*,127.0.0.1:*${RENDER_EXTERNAL_HOSTNAME:+,$RENDER_EXTERNAL_HOSTNAME}}"

echo "Decor MCP: base lista. Iniciando la API en el puerto ${PORT:-8000}."
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}" --proxy-headers --forwarded-allow-ips='*'
