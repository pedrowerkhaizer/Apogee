"""agents/tts.py — TTS agent (Edge-TTS).

Gera arquivos de áudio .mp3 para cada segmento do roteiro de um vídeo usando
Edge-TTS com voz pt-BR-AntonioNeural. Extrai durações reais com mutagen.
Custo zero — edge-tts é gratuito.

Uso manual:
    uv run python agents/tts.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# Garante que a raiz do projeto está em sys.path ao rodar como script
# (deve vir ANTES dos imports third-party pois `from models import ...` é module-level)
sys.path.insert(0, str(Path(__file__).parent.parent))

import json
import logging
import os
import time
from uuid import UUID

import edge_tts
import psycopg2
import psycopg2.extras
from dotenv import load_dotenv
from langsmith import traceable
from mutagen.mp3 import MP3

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# ── Constantes ─────────────────────────────────────────────────────────────────

AGENT_NAME = "tts"
TTS_VOICE = "pt-BR-AntonioNeural"
OUTPUT_BASE = Path("output") / "audio"

# ── Helpers de banco ───────────────────────────────────────────────────────────


def _get_conn() -> psycopg2.extensions.connection:
    db_url = os.getenv("SUPABASE_DB_URL")
    if not db_url:
        raise RuntimeError("SUPABASE_DB_URL não definido no .env")
    return psycopg2.connect(db_url, connect_timeout=10)


def _fetch_script(
    conn: psycopg2.extensions.connection, video_id: UUID
) -> dict:
    """Retorna o script mais recente do vídeo."""
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """
            SELECT s.hook, s.beats, s.payoff, s.cta
            FROM   scripts s
            WHERE  s.video_id = %s
            ORDER  BY s.created_at DESC
            LIMIT  1
            """,
            (str(video_id),),
        )
        row = cur.fetchone()
    if not row:
        raise ValueError(f"Nenhum script encontrado para o vídeo: {video_id}")
    return dict(row)


def _record_agent_run(
    conn: psycopg2.extensions.connection,
    video_id: UUID,
    segments: list[str],
    durations: dict[str, float],
    output_dir: str,
    duration_ms: int,
    status: str,
    error_message: str | None = None,
) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO agent_runs
                (agent_name, video_id, status,
                 input_json, output_json,
                 tokens_input, tokens_output, cost_usd, duration_ms, error_message)
            VALUES (%s, %s, %s, %s, %s, 0, 0, 0.0, %s, %s)
            """,
            (
                AGENT_NAME,
                str(video_id),
                status,
                psycopg2.extras.Json(
                    {"video_id": str(video_id), "segments": segments}
                ),
                psycopg2.extras.Json(
                    {"durations": durations, "output_dir": output_dir}
                ),
                duration_ms,
                error_message,
            ),
        )


# ── Segmentação do script ──────────────────────────────────────────────────────


def _build_segments(script: dict) -> dict[str, str]:
    """Constrói o dict {beat_id: texto} a partir da linha do banco.

    Beats JSONB: lista de {"fact": ..., "analogy": ...}
    Omite o segmento 'cta' se for NULL ou vazio.
    """
    beats_raw = script["beats"]
    if isinstance(beats_raw, str):
        beats_raw = json.loads(beats_raw)

    segments: dict[str, str] = {}
    segments["hook"] = script["hook"]

    for i, beat in enumerate(beats_raw, start=1):
        segments[f"beat_{i}"] = f"{beat['fact']} {beat['analogy']}"

    segments["payoff"] = script["payoff"]

    cta = script.get("cta") or ""
    if cta.strip():
        segments["cta"] = cta

    return segments


# ── Geração de áudio ───────────────────────────────────────────────────────────


def _generate_segment(text: str, output_path: Path) -> float:
    """Gera .mp3 para um segmento e retorna a duração em segundos."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    communicate = edge_tts.Communicate(text, TTS_VOICE)
    communicate.save_sync(str(output_path))
    audio = MP3(str(output_path))
    return round(audio.info.length, 3)


# ── Agente principal ───────────────────────────────────────────────────────────


@traceable(name=AGENT_NAME)
def generate_audio(video_id: UUID) -> dict[str, float]:
    """Gera arquivos .mp3 para cada segmento do script do vídeo.

    Args:
        video_id: UUID do vídeo em videos.

    Returns:
        Dict {beat_id: duration_sec} com a duração real de cada segmento.
    """
    t0 = time.monotonic()
    conn = _get_conn()
    durations: dict[str, float] = {}
    segments_list: list[str] = []
    output_dir = str(OUTPUT_BASE / str(video_id))

    try:
        script = _fetch_script(conn, video_id)
        segments = _build_segments(script)
        segments_list = list(segments.keys())
        log.info("Gerando áudio para vídeo %s — %d segmentos", str(video_id)[:8], len(segments))

        for beat_id, text in segments.items():
            out_path = OUTPUT_BASE / str(video_id) / f"{beat_id}.mp3"
            log.info("  [%s] %d chars → %s", beat_id, len(text), out_path)
            duration = _generate_segment(text, out_path)
            durations[beat_id] = duration
            log.info("    %.2fs", duration)

        duration_ms = int((time.monotonic() - t0) * 1000)
        total_sec = round(sum(durations.values()), 2)
        log.info(
            "generate_audio concluído: %dms | total_audio=%.2fs | dir=%s",
            duration_ms, total_sec, output_dir,
        )

        _record_agent_run(
            conn, video_id, segments_list, durations, output_dir,
            duration_ms, "success",
        )
        conn.commit()

        return durations

    except Exception as exc:
        conn.rollback()
        duration_ms = int((time.monotonic() - t0) * 1000)
        log.error("generate_audio falhou: %s", exc)
        try:
            _record_agent_run(
                conn, video_id, segments_list, {}, output_dir,
                duration_ms, "failed", str(exc),
            )
            conn.commit()
        except Exception:
            pass
        raise

    finally:
        conn.close()


# ── Execução manual ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    _db_url = os.getenv("SUPABASE_DB_URL")
    if not _db_url:
        print("SUPABASE_DB_URL não definido no .env")
        sys.exit(1)

    _conn = psycopg2.connect(_db_url, connect_timeout=10)
    with _conn.cursor() as _cur:
        _cur.execute(
            """
            SELECT v.id, t.title
            FROM   videos v
            JOIN   topics t  ON t.id = v.topic_id
            JOIN   scripts s ON s.video_id = v.id
            WHERE  v.status = 'scripted'
            ORDER  BY v.updated_at ASC
            LIMIT  1
            """
        )
        _row = _cur.fetchone()
    _conn.close()

    if not _row:
        print("Nenhum vídeo com status='scripted' encontrado.")
        print("Execute primeiro: uv run python agents/scriptwriter.py")
        sys.exit(1)

    _video_id, _title = _row
    print(f"Vídeo:  [{str(_video_id)[:8]}] {_title}")
    print("Iniciando generate_audio...\n")

    _durations = generate_audio(UUID(str(_video_id)))

    print(f"\n{'─' * 60}")
    print("Durações por segmento:")
    for _beat, _sec in _durations.items():
        print(f"  {_beat:<10} {_sec:.3f}s")
    print(f"  {'TOTAL':<10} {sum(_durations.values()):.3f}s")
    print(f"\nArquivos em: output/audio/{str(_video_id)[:8]}…/")
