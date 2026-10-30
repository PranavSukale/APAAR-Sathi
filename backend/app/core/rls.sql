-- RLS + least-privilege app role setup. Runs as table owner (apaar_owner).
-- The app role (apaar_app) is NOT the owner and cannot bypass RLS.

-- 1. Application role.
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{app_user}') THEN
        EXECUTE format('CREATE ROLE %I LOGIN PASSWORD %L', '{app_user}', '{app_password}');
    END IF;
END$$;

GRANT USAGE ON SCHEMA public TO "{app_user}";
-- DML on all tables for the app role...
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO "{app_user}";
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO "{app_user}";
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO "{app_user}";
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT USAGE, SELECT ON SEQUENCES TO "{app_user}";

-- 2. audit_events: append + read only for the app role (no UPDATE/DELETE).
REVOKE UPDATE, DELETE ON audit_events FROM "{app_user}";

-- 3. Row-level security on institution-scoped tables.
-- Helper: current scope as uuid[].
CREATE OR REPLACE FUNCTION app_scope_ids() RETURNS uuid[] AS $$
    SELECT CASE
        WHEN coalesce(current_setting('app.scope_ids', true), '') = '' THEN ARRAY[]::uuid[]
        ELSE string_to_array(current_setting('app.scope_ids', true), ',')::uuid[]
    END;
$$ LANGUAGE sql STABLE;

CREATE OR REPLACE FUNCTION app_role() RETURNS text AS $$
    SELECT coalesce(current_setting('app.role', true), '');
$$ LANGUAGE sql STABLE;

-- Tables keyed directly by institution_id.
DO $$
DECLARE t text;
BEGIN
    FOREACH t IN ARRAY ARRAY[
        'institutions','programs','import_batches','mapping_profiles',
        'student_records','enrolment_episodes','exceptions','cases'
    ] LOOP
        EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', t);
        EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY', t);
        EXECUTE format('DROP POLICY IF EXISTS inst_scope ON %I', t);
        IF t = 'institutions' THEN
            EXECUTE format($f$
                CREATE POLICY inst_scope ON %I USING (
                    app_role() IN ('AICTE_REVIEWER','AICTE_SUPERVISOR','AUDITOR','ADMIN')
                    OR id = ANY(app_scope_ids())
                ) WITH CHECK (
                    app_role() IN ('AICTE_REVIEWER','AICTE_SUPERVISOR','AUDITOR','ADMIN')
                    OR id = ANY(app_scope_ids())
                )$f$, t);
        ELSE
            EXECUTE format($f$
                CREATE POLICY inst_scope ON %I USING (
                    app_role() IN ('AICTE_REVIEWER','AICTE_SUPERVISOR','AUDITOR','ADMIN')
                    OR institution_id = ANY(app_scope_ids())
                ) WITH CHECK (
                    app_role() IN ('AICTE_REVIEWER','AICTE_SUPERVISOR','AUDITOR','ADMIN')
                    OR institution_id = ANY(app_scope_ids())
                )$f$, t);
        END IF;
    END LOOP;
END$$;

-- import_row_errors and institution_responses are scoped via their parent.
ALTER TABLE import_row_errors ENABLE ROW LEVEL SECURITY;
ALTER TABLE import_row_errors FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS inst_scope ON import_row_errors;
CREATE POLICY inst_scope ON import_row_errors USING (
    app_role() IN ('AICTE_REVIEWER','AICTE_SUPERVISOR','AUDITOR','ADMIN')
    OR batch_id IN (SELECT id FROM import_batches WHERE institution_id = ANY(app_scope_ids()))
) WITH CHECK (
    app_role() IN ('AICTE_REVIEWER','AICTE_SUPERVISOR','AUDITOR','ADMIN')
    OR batch_id IN (SELECT id FROM import_batches WHERE institution_id = ANY(app_scope_ids()))
);

ALTER TABLE institution_responses ENABLE ROW LEVEL SECURITY;
ALTER TABLE institution_responses FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS inst_scope ON institution_responses;
CREATE POLICY inst_scope ON institution_responses USING (
    app_role() IN ('AICTE_REVIEWER','AICTE_SUPERVISOR','AUDITOR','ADMIN')
    OR case_id IN (SELECT id FROM cases WHERE institution_id = ANY(app_scope_ids()))
) WITH CHECK (
    app_role() IN ('AICTE_REVIEWER','AICTE_SUPERVISOR','AUDITOR','ADMIN')
    OR case_id IN (SELECT id FROM cases WHERE institution_id = ANY(app_scope_ids()))
);
