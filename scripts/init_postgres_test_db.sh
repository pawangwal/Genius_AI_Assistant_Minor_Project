#!/bin/bash
set -e

TEST_USER="${POSTGRES_TEST_USER:-genius_test}"
TEST_PASS="${POSTGRES_TEST_PASSWORD:-$POSTGRES_PASSWORD}"
TEST_DB="${POSTGRES_TEST_DB:-genius_ai_test}"

if [ -z "$TEST_PASS" ]; then
    echo "ERROR: PostgreSQL test password must be supplied via POSTGRES_TEST_PASSWORD or POSTGRES_PASSWORD environment variable." >&2
    exit 1
fi

# 1. Provision isolated test database, enforce primary database isolation, and configure dedicated test role
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    SELECT 'CREATE DATABASE $TEST_DB'
    WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = '$TEST_DB')\gexec

    -- Isolate primary database: Prevent non-primary roles from connecting
    REVOKE CONNECT ON DATABASE "$POSTGRES_DB" FROM PUBLIC;
    GRANT CONNECT ON DATABASE "$POSTGRES_DB" TO "$POSTGRES_USER";

    -- Create or update dedicated restricted test role
    DO \$\$
    BEGIN
      IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = '$TEST_USER') THEN
        CREATE ROLE $TEST_USER WITH LOGIN PASSWORD '$TEST_PASS';
      ELSE
        ALTER ROLE $TEST_USER WITH PASSWORD '$TEST_PASS';
      END IF;
    END
    \$\$;

    -- Grant full privileges on test DB to dedicated test user
    GRANT ALL PRIVILEGES ON DATABASE "$TEST_DB" TO $TEST_USER;
EOSQL

# 2. Grant schema privileges inside the test database
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$TEST_DB" <<-EOSQL
    GRANT ALL ON SCHEMA public TO $TEST_USER;
    GRANT ALL ON ALL TABLES IN SCHEMA public TO $TEST_USER;
    GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO $TEST_USER;
    ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO $TEST_USER;
    ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO $TEST_USER;
EOSQL
