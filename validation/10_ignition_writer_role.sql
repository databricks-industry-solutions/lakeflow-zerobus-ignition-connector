-- =============================================================================
-- Dedicated least-privilege Postgres role for the Ignition connector to write
-- into a LakeTS ChronoTable on Lakebase (native password auth).
--
-- PREREQ (once per project): native Postgres login must be enabled on the
-- Lakebase Autoscaling project (off by default):
--   databricks postgres update-project projects/<proj> spec.enable_pg_native_login \
--     --json '{"spec":{"enable_pg_native_login":true}}' -p <profile>
--
-- Run this as a superuser/owner session (e.g. via `databricks psql`). Set the
-- password via psql variable:  -v ign_pw="'<STRONG_PASSWORD>'"  (note the inner
-- quotes), or edit the CREATE/ALTER below. Connector then uses role
-- ignition_writer + that password with sslmode=require.
--
-- Grants match the connector's INSERT path ONLY (it never UPDATEs/DELETEs the
-- ChronoTable). A single INSERT fires three SECURITY INVOKER triggers:
--   * LVC upsert           -> INSERT/UPDATE on public._lvc_<table>
--   * rollup invalidation  -> INSERT/UPDATE on lakets._rollup_invalidation_log (+ its sequence)
--   * CDF sync (if enabled)-> INSERT on lakets_cdf._shadow_<table>
-- so the role needs USAGE + those DML verbs (NOT delete/truncate/create) across
-- public, lakets, lakets_cdf, plus EXECUTE on lakets functions and sequence USAGE.
-- =============================================================================

-- Create or reset the login role. Replace the password (or pass -v ign_pw=...).
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='ignition_writer') THEN
    ALTER ROLE ignition_writer LOGIN PASSWORD :ign_pw;
  ELSE
    CREATE ROLE ignition_writer LOGIN PASSWORD :ign_pw;
  END IF;
END $$;

-- Clean slate so re-runs converge to least privilege.
REVOKE ALL ON ALL TABLES    IN SCHEMA public, lakets, lakets_cdf FROM ignition_writer;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA public, lakets, lakets_cdf FROM ignition_writer;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA lakets FROM ignition_writer;
REVOKE CREATE ON SCHEMA public FROM ignition_writer;

GRANT CONNECT ON DATABASE databricks_postgres TO ignition_writer;

-- public: INSERT into the ChronoTable + INSERT/UPDATE for the LVC upsert. No DELETE/TRUNCATE/CREATE.
GRANT USAGE ON SCHEMA public TO ignition_writer;
GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA public TO ignition_writer;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO ignition_writer;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE ON TABLES TO ignition_writer;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO ignition_writer;

-- lakets: rollup-invalidation trigger writes the log (INSERT/UPDATE + sequence); trigger fns need EXECUTE; reads registry.
GRANT USAGE ON SCHEMA lakets TO ignition_writer;
GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA lakets TO ignition_writer;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA lakets TO ignition_writer;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA lakets TO ignition_writer;
ALTER DEFAULT PRIVILEGES IN SCHEMA lakets GRANT SELECT, INSERT, UPDATE ON TABLES TO ignition_writer;
ALTER DEFAULT PRIVILEGES IN SCHEMA lakets GRANT USAGE, SELECT ON SEQUENCES TO ignition_writer;
ALTER DEFAULT PRIVILEGES IN SCHEMA lakets GRANT EXECUTE ON FUNCTIONS TO ignition_writer;

-- lakets_cdf: sync trigger inserts into the shadow table (only when enable_sync is ON).
GRANT USAGE ON SCHEMA lakets_cdf TO ignition_writer;
GRANT SELECT, INSERT ON ALL TABLES IN SCHEMA lakets_cdf TO ignition_writer;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA lakets_cdf TO ignition_writer;
ALTER DEFAULT PRIVILEGES IN SCHEMA lakets_cdf GRANT SELECT, INSERT ON TABLES TO ignition_writer;
ALTER DEFAULT PRIVILEGES IN SCHEMA lakets_cdf GRANT USAGE, SELECT ON SEQUENCES TO ignition_writer;

SELECT 'ignition_writer role + least-privilege grants applied' AS status;
