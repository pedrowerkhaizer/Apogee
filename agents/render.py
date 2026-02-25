"""agents/render.py — Render agent (Remotion via subprocess).

Orquestra o render de um vídeo:
  1. Prepara assets (áudio + input_props.json) via scripts/prepare_remotion.py
  2. Sobrescreve input_props.json com showTimer=False para o render final
  3. Chama `npx remotion render` e exibe stdout em tempo real
  4. Persiste resultado em renders + agent_runs
  5. Atualiza videos.status = 'rendered'

Uso manual:
    uv run python agents/render.py --video-id <UUID>
"""

from __future__ import annotations

import sys
from pathlib import Path

# Garante que a raiz do projeto está em sys.path ao rodar como script
sys.path.insert(0, str(Path(__file__).parent.parent))

import json
import logging
import os
import subprocess
import time
from uuid import UUID

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

AGENT_NAME = "render"
ROOT = Path(__file__).parent.parent
REMOTION_DIR = ROOT / "remotion"
OUTPUT_RENDERS = ROOT / "output" / "renders"
STORYBOARD_BASE = ROOT / "output" / "storyboards"

# ── Helpers de banco ───────────────────────────────────────────────────────────


def _get_conn() -> psycopg2.extensions.connection:
    db_url = os.getenv("SUPABASE_DB_URL")
    if not db_url:
        raise RuntimeError("SUPABASE_DB_URL não definido no .env")
    return psycopg2.connect(db_url, connect_timeout=10)


def _persist_render(
    conn: psycopg2.extensions.connection,
    video_id: UUID,
    output_path: Path,
    file_size_bytes: int,
    duration_secs: float,
    render_time_sec: float,
) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO renders
                (video_id, file_path, duration_secs, file_size_bytes,
                 resolution, codec, fps, render_time_sec)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                str(video_id),
                str(output_path),
                duration_secs,
                file_size_bytes,
                "1080x1920",
                "h264",
                30,
                round(render_time_sec, 2),
            ),
        )


def _update_video_status(
    conn: psycopg2.extensions.connection, video_id: UUID
) -> None:
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE videos SET status = 'rendered', updated_at = NOW() WHERE id = %s",
            (str(video_id),),
        )


def _record_agent_run(
    conn: psycopg2.extensions.connection,
    video_id: UUID,
    output_path: str,
    file_size_mb: float,
    render_time_sec: float,
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
                        "output_path": output_path,
                        "file_size_mb": file_size_mb,
                        "render_time_sec": render_time_sec,
                    }
                ),
                duration_ms,
                error_message,
            ),
        )


# ── Subprocessos ───────────────────────────────────────────────────────────────


def _run_prepare_assets(video_id: UUID) -> None:
    """Copia áudios e escreve input_props.json via scripts/prepare_remotion.py."""
    log.info("Preparando assets Remotion para vídeo %s…", str(video_id)[:8])
    result = subprocess.run(
        ["uv", "run", "scripts/prepare_remotion.py", "--video-id", str(video_id)],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"prepare_remotion.py falhou (exit {result.returncode}):\n{result.stderr}"
        )
    for line in result.stdout.strip().splitlines():
        log.info("  %s", line)


def _write_render_props(video_id: UUID) -> float:
    """Sobrescreve input_props.json com showTimer=False para o render final.

    Returns:
        total_duration do storyboard (segundos).
    """
    storyboard_path = STORYBOARD_BASE / f"{video_id}.json"
    storyboard = json.loads(storyboard_path.read_text())
    render_props = {"storyboard": storyboard, "showTimer": False}
    props_path = REMOTION_DIR / "public" / "input_props.json"
    props_path.write_text(json.dumps(render_props, ensure_ascii=False, indent=2))
    log.info("input_props.json atualizado (showTimer=false)")
    return float(storyboard["total_duration"])


def _run_remotion_render(video_id: UUID, output_path: Path) -> None:
    """Chama npx remotion render e exibe stdout em tempo real."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    # O output_path é relativo ao remotion/ (cwd do subprocess)
    rel_output = Path("..") / output_path.relative_to(ROOT)

    cmd = [
        "npx", "remotion", "render", "ShortExplainer",
        str(rel_output),
        "--props=public/input_props.json",
        "--log=verbose",
    ]
    log.info("Iniciando render: %s", " ".join(cmd))

    process = subprocess.Popen(
        cmd,
        cwd=str(REMOTION_DIR),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )

    assert process.stdout is not None
    for line in process.stdout:
        print(line, end="", flush=True)

    process.wait()
    if process.returncode != 0:
        raise RuntimeError(
            f"npx remotion render falhou com exit code {process.returncode}"
        )


# ── Agente principal ───────────────────────────────────────────────────────────


@traceable(name=AGENT_NAME)
def render_video(video_id: UUID) -> dict:
    """Renderiza o vídeo via Remotion e persiste o resultado no banco.

    Args:
        video_id: UUID do vídeo em videos.

    Returns:
        Dict com output_path, file_size_mb e render_time_sec.
    """
    t0 = time.monotonic()
    conn = _get_conn()
    output_path = OUTPUT_RENDERS / f"{video_id}.mp4"
    file_size_mb = 0.0
    render_time_sec = 0.0

    try:
        # 1. Prepara assets (copia mp3s + escreve input_props.json)
        _run_prepare_assets(video_id)

        # 2. Sobrescreve input_props.json com showTimer=False
        duration_secs = _write_render_props(video_id)

        # 3. Render Remotion
        render_start = time.monotonic()
        _run_remotion_render(video_id, output_path)
        render_time_sec = round(time.monotonic() - render_start, 2)

        # 4. Verifica e mede o arquivo gerado
        if not output_path.exists():
            raise FileNotFoundError(f"Arquivo de render não encontrado: {output_path}")
        file_size_bytes = output_path.stat().st_size
        file_size_mb = round(file_size_bytes / 1024 / 1024, 2)

        log.info(
            "Render concluído: %.1fs | %.2f MB | %s",
            render_time_sec, file_size_mb, output_path,
        )

        # 5. Persiste no banco
        duration_ms = int((time.monotonic() - t0) * 1000)
        _persist_render(conn, video_id, output_path, file_size_bytes, duration_secs, render_time_sec)
        _update_video_status(conn, video_id)
        _record_agent_run(
            conn, video_id, str(output_path), file_size_mb, render_time_sec,
            duration_ms, "success",
        )
        conn.commit()

        return {
            "output_path": str(output_path),
            "file_size_mb": file_size_mb,
            "render_time_sec": render_time_sec,
        }

    except Exception as exc:
        conn.rollback()
        duration_ms = int((time.monotonic() - t0) * 1000)
        log.error("render_video falhou: %s", exc)
        try:
            _record_agent_run(
                conn, video_id, str(output_path), file_size_mb, render_time_sec,
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
    import argparse

    _parser = argparse.ArgumentParser(description="Render agent — renderiza vídeo via Remotion")
    _parser.add_argument(
        "--video-id",
        metavar="UUID",
        help="UUID do vídeo (opcional; padrão: primeiro com status='scripted')",
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
                WHERE  v.status = 'scripted'
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
            print("Nenhum vídeo com status='scripted' encontrado.")
            print("Execute o pipeline completo antes de renderizar.")
        sys.exit(1)

    _video_id, _title = _row
    print(f"Vídeo:  [{str(_video_id)[:8]}] {_title}")
    print("Iniciando render_video...\n")

    _result = render_video(UUID(str(_video_id)))

    print(f"\n{'─' * 60}")
    print(f"Output:       {_result['output_path']}")
    print(f"Tamanho:      {_result['file_size_mb']} MB")
    print(f"Tempo render: {_result['render_time_sec']}s")
