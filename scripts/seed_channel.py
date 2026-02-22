"""scripts/seed_channel.py – Insere canal placeholder em channel_config.

Idempotente: usa ON CONFLICT DO NOTHING baseado no channel_name.
Requer que as migrations já tenham sido aplicadas.

Uso:
    uv run python scripts/seed_channel.py
"""

from __future__ import annotations

import logging
import os
import sys

import psycopg2
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# ── Dados do canal ────────────────────────────────────────────
CHANNEL_DATA = {
    "channel_name": "Apogee Engine",
    "niche": "tecnologia e inteligência artificial",
    "tone": "educativo-direto",
    "target_audience": (
        "Profissionais e entusiastas de tecnologia, 25–40 anos, "
        "interessados em IA aplicada, automação e produtividade"
    ),
    "language": "pt-BR",
    "weekly_target": 2,
    "youtube_channel_id": None,  # preencher após criar o canal no YouTube
}

INSERT_SQL = """
INSERT INTO channel_config (
    channel_name, niche, tone, target_audience,
    language, weekly_target, youtube_channel_id
)
VALUES (
    %(channel_name)s, %(niche)s, %(tone)s, %(target_audience)s,
    %(language)s, %(weekly_target)s, %(youtube_channel_id)s
)
ON CONFLICT (channel_name) DO NOTHING
RETURNING id;
"""


def seed_channel() -> None:
    """Insere o canal padrão em channel_config (idempotente)."""
    db_url = os.getenv("SUPABASE_DB_URL")
    if not db_url:
        log.error("SUPABASE_DB_URL não definido no .env")
        sys.exit(1)

    try:
        conn = psycopg2.connect(db_url, connect_timeout=10)
    except Exception as exc:
        log.error("Falha ao conectar: %s", exc)
        sys.exit(1)

    try:
        with conn.cursor() as cur:
            cur.execute(INSERT_SQL, CHANNEL_DATA)
            row = cur.fetchone()
            if row:
                log.info("Canal inserido com id=%s", row[0])
            else:
                log.info("Canal '%s' já existe — nada inserido.", CHANNEL_DATA["channel_name"])
        conn.commit()
    except Exception as exc:
        conn.rollback()
        log.error("Falha ao inserir canal: %s", exc)
        sys.exit(1)
    finally:
        conn.close()


if __name__ == "__main__":
    seed_channel()
