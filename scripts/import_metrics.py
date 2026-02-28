#!/usr/bin/env python3
"""scripts/import_metrics.py — Import YouTube Studio CSV metrics into performance_daily.

Lê um CSV exportado do YouTube Studio e faz upsert das métricas diárias
na tabela performance_daily do Supabase.

Uso:
    uv run python scripts/import_metrics.py --file /path/to/metrics.csv

Colunas obrigatórias no CSV:
    video_id, date, views, avg_view_duration_sec, ctr, likes, shares

    Onde `video_id` é o ID do vídeo no YouTube (ex: dQw4w9WgXcQ),
    que será resolvido para o UUID interno via videos.youtube_video_id.
"""

from __future__ import annotations

import csv
import logging
import os
import sys
from pathlib import Path

# Adiciona raiz do projeto ao sys.path (2 níveis acima de scripts/)
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

load_dotenv()

import psycopg2

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

EXPECTED_COLUMNS = {"video_id", "date", "views", "avg_view_duration_sec", "ctr", "likes", "shares"}

# SQL: upsert com detecção de INSERT vs UPDATE via xmax
UPSERT_SQL = """
INSERT INTO performance_daily (
    video_id,
    report_date,
    views,
    avg_view_duration_sec,
    ctr,
    likes,
    shares
)
VALUES (
    %(video_id)s,
    %(report_date)s,
    %(views)s,
    %(avg_view_duration_sec)s,
    %(ctr)s,
    %(likes)s,
    %(shares)s
)
ON CONFLICT (video_id, report_date) DO UPDATE SET
    views                 = EXCLUDED.views,
    avg_view_duration_sec = EXCLUDED.avg_view_duration_sec,
    ctr                   = EXCLUDED.ctr,
    likes                 = EXCLUDED.likes,
    shares                = EXCLUDED.shares
RETURNING (xmax = 0) AS inserted;
"""

LOOKUP_SQL = "SELECT id FROM videos WHERE youtube_video_id = %s LIMIT 1;"


def _get_db_url() -> str:
    """Lê SUPABASE_DB_URL do ambiente e falha com mensagem clara se ausente."""
    url = os.getenv("SUPABASE_DB_URL")
    if not url:
        log.error("Variável de ambiente SUPABASE_DB_URL não definida.")
        sys.exit(1)
    return url


def validate_columns(fieldnames: list[str] | None) -> None:
    """Valida que o CSV contém todas as colunas obrigatórias.

    Raises:
        SystemExit: Se colunas obrigatórias estiverem faltando.
    """
    if not fieldnames:
        log.error("CSV vazio ou sem cabeçalho.")
        sys.exit(1)

    actual = set(f.strip() for f in fieldnames)
    missing = EXPECTED_COLUMNS - actual
    if missing:
        log.error(
            "Colunas obrigatórias faltando no CSV: %s\n"
            "Colunas encontradas: %s\n"
            "Colunas obrigatórias: %s",
            sorted(missing),
            sorted(actual),
            sorted(EXPECTED_COLUMNS),
        )
        sys.exit(1)


def parse_row(row: dict) -> dict | None:
    """Converte e valida os valores de uma linha do CSV.

    Returns:
        Dicionário com valores tipados, ou None se a linha for inválida.
    """
    try:
        return {
            "youtube_video_id": row["video_id"].strip(),
            "report_date": row["date"].strip(),
            "views": int(row["views"]),
            "avg_view_duration_sec": float(row["avg_view_duration_sec"]),
            "ctr": float(row["ctr"]),
            "likes": int(row["likes"]),
            "shares": int(row["shares"]),
        }
    except (ValueError, KeyError) as exc:
        log.warning("Linha inválida (erro de conversão): %s — %s", dict(row), exc)
        return None


def import_metrics(file_path: str) -> None:
    """Importa métricas do CSV para a tabela performance_daily.

    Para cada linha do CSV:
    1. Resolve youtube_video_id -> UUID interno em videos
    2. Faz upsert em performance_daily
    3. Contabiliza inserções, atualizações e erros

    Args:
        file_path: Caminho para o arquivo CSV do YouTube Studio.
    """
    csv_path = Path(file_path)
    if not csv_path.exists():
        log.error("Arquivo não encontrado: %s", file_path)
        sys.exit(1)
    if not csv_path.is_file():
        log.error("Caminho não é um arquivo: %s", file_path)
        sys.exit(1)

    db_url = _get_db_url()

    log.info("Conectando ao banco de dados...")
    try:
        conn = psycopg2.connect(db_url, connect_timeout=10)
    except Exception as exc:
        log.error("Falha ao conectar ao banco: %s", exc)
        sys.exit(1)

    # autocommit=True para que cada upsert seja independente;
    # erros em uma linha não afetam as demais.
    conn.autocommit = True

    inserted_count = 0
    updated_count = 0
    error_count = 0
    total_rows = 0

    log.info("Lendo CSV: %s", csv_path)

    try:
        with csv_path.open(newline="", encoding="utf-8-sig") as fh:
            reader = csv.DictReader(fh)
            validate_columns(reader.fieldnames)

            for row in reader:
                total_rows += 1

                parsed = parse_row(row)
                if parsed is None:
                    error_count += 1
                    continue

                youtube_video_id = parsed["youtube_video_id"]

                # Lookup: youtube_video_id -> UUID interno
                try:
                    with conn.cursor() as cur:
                        cur.execute(LOOKUP_SQL, (youtube_video_id,))
                        result = cur.fetchone()
                except Exception as exc:
                    log.warning(
                        "Erro ao buscar video_id para %s: %s",
                        youtube_video_id,
                        exc,
                    )
                    error_count += 1
                    continue

                if result is None:
                    log.warning(
                        "youtube_video_id '%s' não encontrado na tabela videos — linha ignorada.",
                        youtube_video_id,
                    )
                    error_count += 1
                    continue

                internal_video_id = result[0]

                # Upsert em performance_daily
                upsert_params = {
                    "video_id": internal_video_id,
                    "report_date": parsed["report_date"],
                    "views": parsed["views"],
                    "avg_view_duration_sec": parsed["avg_view_duration_sec"],
                    "ctr": parsed["ctr"],
                    "likes": parsed["likes"],
                    "shares": parsed["shares"],
                }

                try:
                    with conn.cursor() as cur:
                        cur.execute(UPSERT_SQL, upsert_params)
                        upsert_result = cur.fetchone()
                        was_inserted = upsert_result[0] if upsert_result else True
                except Exception as exc:
                    log.warning(
                        "Erro ao fazer upsert para video %s / data %s: %s",
                        youtube_video_id,
                        parsed["report_date"],
                        exc,
                    )
                    error_count += 1
                    continue

                if was_inserted:
                    inserted_count += 1
                    log.debug(
                        "INSERIDO: %s / %s",
                        youtube_video_id,
                        parsed["report_date"],
                    )
                else:
                    updated_count += 1
                    log.debug(
                        "ATUALIZADO: %s / %s",
                        youtube_video_id,
                        parsed["report_date"],
                    )

    except Exception as exc:
        log.error("Erro inesperado ao processar CSV: %s", exc)
        conn.close()
        sys.exit(1)
    finally:
        conn.close()

    # Resumo final
    print(
        f"\n--- Resumo da importacao ---\n"
        f"Total de linhas no CSV : {total_rows}\n"
        f"Linhas importadas      : {inserted_count}\n"
        f"Linhas atualizadas     : {updated_count}\n"
        f"Erros                  : {error_count}\n"
        f"----------------------------"
    )

    if error_count > 0:
        log.warning("%d linha(s) com erro. Verifique os logs acima.", error_count)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Import YouTube Studio CSV metrics into performance_daily."
    )
    parser.add_argument(
        "--file",
        required=True,
        metavar="PATH",
        help="Caminho para o arquivo CSV exportado do YouTube Studio.",
    )
    args = parser.parse_args()

    import_metrics(args.file)
