"""scripts/apply_migrations.py – Apogee migration runner.

Lê todos os arquivos migrations/*.sql em ordem numérica e executa
no Supabase via psycopg2 usando SUPABASE_DB_URL do .env.

Uso:
    uv run python scripts/apply_migrations.py
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

import psycopg2
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

MIGRATIONS_DIR = Path(__file__).parent.parent / "migrations"


def get_migration_files() -> list[Path]:
    """Retorna arquivos .sql da pasta migrations/ em ordem numérica."""
    files = sorted(MIGRATIONS_DIR.glob("*.sql"))
    if not files:
        log.warning("Nenhum arquivo .sql encontrado em %s", MIGRATIONS_DIR)
    return files


def apply_migrations() -> None:
    """Executa todos os arquivos de migration em ordem, com rollback em falha."""
    db_url = os.getenv("SUPABASE_DB_URL")
    if not db_url:
        log.error("SUPABASE_DB_URL não definido no .env")
        sys.exit(1)

    files = get_migration_files()
    if not files:
        log.info("Nada a executar.")
        return

    log.info("Conectando ao banco de dados...")
    try:
        conn = psycopg2.connect(db_url, connect_timeout=10)
    except Exception as exc:
        log.error("Falha ao conectar: %s", exc)
        sys.exit(1)

    conn.autocommit = False

    for migration_file in files:
        log.info("Aplicando: %s", migration_file.name)
        sql = migration_file.read_text(encoding="utf-8")

        try:
            with conn.cursor() as cur:
                cur.execute(sql)
            conn.commit()
            log.info("✓ %s aplicado com sucesso.", migration_file.name)
        except Exception as exc:
            conn.rollback()
            log.error("✗ Falha em %s: %s", migration_file.name, exc)
            conn.close()
            sys.exit(1)

    conn.close()
    log.info("Todas as migrations aplicadas com sucesso.")


if __name__ == "__main__":
    apply_migrations()
