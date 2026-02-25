-- =============================================================
-- 003_assets_origin_checksum.sql
-- Apogee Engine — adiciona colunas origin e checksum à tabela assets
-- Criado: 2026-02-24
-- Rollback: ALTER TABLE assets DROP COLUMN IF EXISTS origin, DROP COLUMN IF EXISTS checksum;
-- =============================================================

ALTER TABLE assets
    ADD COLUMN IF NOT EXISTS origin   TEXT    NOT NULL DEFAULT 'generated',
    ADD COLUMN IF NOT EXISTS checksum TEXT;
