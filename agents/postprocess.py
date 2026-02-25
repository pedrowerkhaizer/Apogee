"""agents/postprocess.py — Pós-processamento FFmpeg.

Aplica normalização de loudness (LUFS -14), compressão H.264 (CRF 23) e
extrai thumbnail do vídeo renderizado pelo Remotion.

Uso manual:
    uv run python agents/postprocess.py --video-id <UUID>
"""

from __future__ import annotations

import sys
from pathlib import Path

# Garante que a raiz do projeto está em sys.path ao rodar como script
sys.path.insert(0, str(Path(__file__).parent.parent))

import logging
import os
import time
from uuid import UUID

import ffmpeg
import psycopg2
import psycopg2.extras
from dotenv import load_dotenv
from langsmith import traceable

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# ── Constantes ─────────────────────────────────────────────────────────────────

AGENT_NAME = "postprocess"
ROOT = Path(__file__).parent.parent
OUTPUT_FINAL = ROOT / "output" / "final"
OUTPUT_THUMBNAILS = ROOT / "output" / "thumbnails"

# ── Helpers de banco ───────────────────────────────────────────────────────────


def _get_conn() -> psycopg2.extensions.connection:
    db_url = os.getenv("SUPABASE_DB_URL")
    if not db_url:
        raise RuntimeError("SUPABASE_DB_URL não definido no .env")
    return psycopg2.connect(db_url, connect_timeout=10)


def _fetch_latest_render(
    conn: psycopg2.extensions.connection, video_id: UUID
) -> dict:
    """Busca o render mais recente do vídeo."""
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """
            SELECT id, file_path, duration_secs, file_size_bytes
            FROM   renders
            WHERE  video_id = %s
            ORDER  BY created_at DESC
            LIMIT  1
            """,
            (str(video_id),),
        )
        row = cur.fetchone()
    if not row:
        raise RuntimeError(f"Nenhum render encontrado para video_id={video_id}")
    return dict(row)


def _update_render(
    conn: psycopg2.extensions.connection,
    render_id: str,
    final_path: Path,
    thumbnail_path: Path,
    file_size_bytes: int,
) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE renders
            SET    final_path = %s,
                   thumbnail_path = %s,
                   file_size_bytes = %s,
                   lufs = -14.0
            WHERE  id = %s
            """,
            (str(final_path), str(thumbnail_path), file_size_bytes, render_id),
        )


def _update_video_status(
    conn: psycopg2.extensions.connection, video_id: UUID
) -> None:
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE videos SET status = 'published', updated_at = NOW() WHERE id = %s",
            (str(video_id),),
        )


def _record_agent_run(
    conn: psycopg2.extensions.connection,
    video_id: UUID,
    final_path: str,
    thumbnail_path: str,
    file_size_mb: float,
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
                psycopg2.extras.Json({"video_id": str(video_id)}),
                psycopg2.extras.Json(
                    {
                        "final_path": final_path,
                        "thumbnail_path": thumbnail_path,
                        "file_size_mb": file_size_mb,
                    }
                ),
                duration_ms,
                error_message,
            ),
        )


# ── Processamento FFmpeg ────────────────────────────────────────────────────────


def _apply_ffmpeg(input_path: Path, output_path: Path) -> None:
    """Aplica normalização de loudness (LUFS -14) + re-encode H.264 CRF 23."""
    log.info("Aplicando loudnorm + H.264 CRF 23: %s → %s", input_path.name, output_path.name)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    stream = ffmpeg.input(str(input_path))
    audio = stream.audio.filter(
        "loudnorm",
        I=-14,
        LRA=11,
        TP=-1.5,
    )
    video = stream.video

    (
        ffmpeg
        .output(
            video,
            audio,
            str(output_path),
            vcodec="libx264",
            crf=23,
            preset="medium",
            acodec="aac",
            audio_bitrate="192k",
        )
        .overwrite_output()
        .run(quiet=True)
    )
    log.info("Vídeo final salvo: %s", output_path)


def _extract_thumbnail(video_path: Path, thumbnail_path: Path) -> None:
    """Extrai frame do segundo 3 como thumbnail JPEG."""
    log.info("Extraindo thumbnail @ 3s: %s", thumbnail_path.name)
    thumbnail_path.parent.mkdir(parents=True, exist_ok=True)

    (
        ffmpeg
        .input(str(video_path), ss=3)
        .output(str(thumbnail_path), vframes=1)
        .overwrite_output()
        .run(quiet=True)
    )
    log.info("Thumbnail salvo: %s", thumbnail_path)


# ── Agente principal ───────────────────────────────────────────────────────────


@traceable(name=AGENT_NAME)
def postprocess(video_id: UUID) -> str:
    """Aplica pós-processamento FFmpeg ao vídeo renderizado.

    Args:
        video_id: UUID do vídeo em videos.

    Returns:
        Caminho absoluto do arquivo final processado.
    """
    t0 = time.monotonic()
    conn = _get_conn()
    final_path = OUTPUT_FINAL / f"{video_id}.mp4"
    thumbnail_path = OUTPUT_THUMBNAILS / f"{video_id}.jpg"
    file_size_mb = 0.0

    try:
        # 1. Busca o render mais recente
        render = _fetch_latest_render(conn, video_id)
        input_path = Path(render["file_path"])

        if not input_path.exists():
            raise FileNotFoundError(f"Arquivo de render não encontrado: {input_path}")

        log.info(
            "Render encontrado: %s (%.1f MB)",
            input_path.name,
            (render["file_size_bytes"] or 0) / 1024 / 1024,
        )

        # 2. Aplica loudnorm + H.264 CRF 23
        _apply_ffmpeg(input_path, final_path)

        # 3. Extrai thumbnail do arquivo final
        _extract_thumbnail(final_path, thumbnail_path)

        # 4. Mede tamanho do arquivo final
        file_size_bytes = final_path.stat().st_size
        file_size_mb = round(file_size_bytes / 1024 / 1024, 2)
        log.info("Arquivo final: %.2f MB", file_size_mb)

        # 5. Persiste no banco
        duration_ms = int((time.monotonic() - t0) * 1000)
        _update_render(conn, render["id"], final_path, thumbnail_path, file_size_bytes)
        _update_video_status(conn, video_id)
        _record_agent_run(
            conn,
            video_id,
            str(final_path),
            str(thumbnail_path),
            file_size_mb,
            duration_ms,
            "success",
        )
        conn.commit()

        log.info("Pós-processamento concluído em %.1fs", time.monotonic() - t0)
        return str(final_path)

    except Exception as exc:
        conn.rollback()
        duration_ms = int((time.monotonic() - t0) * 1000)
        log.error("postprocess falhou: %s", exc)
        try:
            _record_agent_run(
                conn,
                video_id,
                str(final_path),
                str(thumbnail_path),
                file_size_mb,
                duration_ms,
                "failed",
                str(exc),
            )
            conn.commit()
        except Exception:
            pass
        raise

    finally:
        conn.close()


# ── Execução manual ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    _parser = argparse.ArgumentParser(
        description="Postprocess agent — aplica FFmpeg ao vídeo renderizado"
    )
    _parser.add_argument(
        "--video-id",
        metavar="UUID",
        help="UUID do vídeo (opcional; padrão: primeiro com status='rendered')",
    )
    _args = _parser.parse_args()

    _db_url = os.getenv("SUPABASE_DB_URL")
    if not _db_url:
        print("SUPABASE_DB_URL não definido no .env")
        sys.exit(1)

    _conn = psycopg2.connect(_db_url, connect_timeout=10)
    with _conn.cursor() as _cur:
        if _args.video_id:
            _cur.execute(
                """
                SELECT v.id, t.title
                FROM   videos v
                JOIN   topics t ON t.id = v.topic_id
                WHERE  v.id = %s
                """,
                (_args.video_id,),
            )
        else:
            _cur.execute(
                """
                SELECT v.id, t.title
                FROM   videos v
                JOIN   topics t ON t.id = v.topic_id
                WHERE  v.status = 'rendered'
                ORDER  BY v.updated_at ASC
                LIMIT  1
                """
            )
        _row = _cur.fetchone()
    _conn.close()

    if not _row:
        if _args.video_id:
            print(f"Vídeo não encontrado: {_args.video_id}")
        else:
            print("Nenhum vídeo com status='rendered' encontrado.")
            print("Execute o render antes de pós-processar.")
        sys.exit(1)

    _video_id, _title = _row
    print(f"Vídeo:  [{str(_video_id)[:8]}] {_title}")
    print("Iniciando postprocess...\n")

    _final_path = postprocess(UUID(str(_video_id)))

    _thumb = str(OUTPUT_THUMBNAILS / f"{_video_id}.jpg")
    _size = round(Path(_final_path).stat().st_size / 1024 / 1024, 2)

    print(f"\n{'─' * 60}")
    print(f"Final:     {_final_path}")
    print(f"Thumbnail: {_thumb}")
    print(f"Tamanho:   {_size} MB")
    print(f"Status:    published")
