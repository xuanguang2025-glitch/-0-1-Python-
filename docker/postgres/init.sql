# PYTHON LAB —— 生产环境 PostgreSQL 初始化
# 由 docker-compose.yml 挂载到 /docker-entrypoint-initdb.d/01-init.sql
# 仅在数据卷首次初始化时执行（建库后不会重复执行）。
#
# 注意：业务表由 backend 的 Alembic 迁移创建（`alembic upgrade head`），
# 本文件只准备扩展、时区与只读账号。

\set ON_ERROR_STOP on

-- 扩展：uuid 生成 + 模糊检索（pg_trgm）
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";
CREATE EXTENSION IF NOT EXISTS "unaccent";

-- 时区与排序（用 dynamic SQL，避免依赖 psql 变量 :POSTGRES_DB）
DO $$
BEGIN
    EXECUTE format('ALTER DATABASE %I SET timezone TO ''UTC''', current_database());
    EXECUTE format('ALTER DATABASE %I SET client_encoding TO ''UTF8''', current_database());
END
$$;

-- 只读账号（供分析/BI/报表使用，禁止写入）
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'pythonlab_ro') THEN
        CREATE ROLE pythonlab_ro WITH LOGIN PASSWORD 'pythonlab_ro_pass';
    END IF;
END
$$;

GRANT USAGE ON SCHEMA public TO pythonlab_ro;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO pythonlab_ro;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO pythonlab_ro;

DO $$
BEGIN
    EXECUTE format('GRANT CONNECT ON DATABASE %I TO pythonlab_ro', current_database());
EXCEPTION WHEN insufficient_privilege OR undefined_object THEN
    RAISE NOTICE 'grant connect skipped: %', SQLERRM;
END
$$;

-- 常用索引（表存在时才会创建，Alembic 迁移后重复执行亦安全）
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables
               WHERE table_schema = 'public' AND table_name = 'problems') THEN
        CREATE INDEX IF NOT EXISTS idx_problems_title_trgm
            ON problems USING gin (title gin_trgm_ops);
        CREATE INDEX IF NOT EXISTS idx_problems_desc_trgm
            ON problems USING gin (description gin_trgm_ops);
    END IF;

    IF EXISTS (SELECT 1 FROM information_schema.tables
               WHERE table_schema = 'public' AND table_name = 'lessons') THEN
        CREATE INDEX IF NOT EXISTS idx_lessons_title_trgm
            ON lessons USING gin (title gin_trgm_ops);
    END IF;

    IF EXISTS (SELECT 1 FROM information_schema.tables
               WHERE table_schema = 'public' AND table_name = 'submissions') THEN
        CREATE INDEX IF NOT EXISTS idx_submissions_user_created
            ON submissions (user_id, created_at DESC);
        CREATE INDEX IF NOT EXISTS idx_submissions_problem_status
            ON submissions (problem_id, status);
    END IF;
END
$$;
