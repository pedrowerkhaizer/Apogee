-- =============================================================
-- 002_renders_final_path.sql
-- Apogee Engine — adiciona colunas para pós-processamento FFmpeg
-- Criado: 2026-02-24
-- =============================================================

-- Separa o caminho do render bruto (Remotion) do arquivo final (FFmpeg)
ALTER TABLE renders
    ADD COLUMN IF NOT EXISTS final_path TEXT,
    ADD COLUMN IF NOT EXISTS thumbnail_path TEXT,
    ADD COLUMN IF NOT EXISTS fps INTEGER,
    ADD COLUMN IF NOT EXISTS render_time_sec FLOAT;

-- ROLLBACK:
-- ALTER TABLE renders DROP COLUMN IF EXISTS final_path;
-- ALTER TABLE renders DROP COLUMN IF EXISTS thumbnail_path;
-- ALTER TABLE renders DROP COLUMN IF EXISTS fps;
-- ALTER TABLE renders DROP COLUMN IF EXISTS render_time_sec;
