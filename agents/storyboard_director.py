"""agents/storyboard_director.py — Storyboard Director.

Monta storyboard com timestamps precisos a partir das durações reais dos arquivos
de áudio. Rule-based — sem LLM. Custo zero.

Uso manual:
    uv run python agents/storyboard_director.py
    uv run python agents/storyboard_director.py --video-id <UUID>
"""

from __future__ import annotations

import sys
from pathlib import Path

# Garante que a raiz do projeto está em sys.path ao rodar como script
sys.path.insert(0, str(Path(__file__).parent.parent))

import json
import logging
import os
import time
from uuid import UUID

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv
from mutagen.mp3 import MP3

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# ── Constantes ─────────────────────────────────────────────────────────────────

AGENT_NAME = "storyboard_director"
AUDIO_BASE = Path("output") / "audio"
STORYBOARD_BASE = Path("output") / "storyboards"

# Ordem fixa dos segmentos e seus tipos de cena
SEGMENT_ORDER = ["hook", "beat_1", "beat_2", "beat_3", "payoff", "cta"]
SCENE_TYPES: dict[str, str] = {
    "hook": "hook_text",
    "beat_1": "text_animation",
    "beat_2": "text_animation",
    "beat_3": "text_animation",
    "payoff": "payoff_text",
    "cta": "cta_text",
}

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
    storyboard: dict,
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
                psycopg2.extras.Json(storyboard),
                duration_ms,
                error_message,
            ),
        )


# ── Leitura de durações ────────────────────────────────────────────────────────


def _read_durations(video_id: UUID) -> dict[str, float]:
    """Lê durações reais dos .mp3 via mutagen para cada segmento existente."""
    audio_dir = AUDIO_BASE / str(video_id)
    durations: dict[str, float] = {}
    for seg_id in SEGMENT_ORDER:
        mp3_path = audio_dir / f"{seg_id}.mp3"
        if mp3_path.exists():
            audio = MP3(str(mp3_path))
            durations[seg_id] = round(audio.info.length, 3)
    return durations


# ── Montagem de textos por segmento ───────────────────────────────────────────


def _build_texts(script: dict) -> dict[str, str]:
    """Extrai texto de cada segmento a partir do script."""
    beats_raw = script["beats"]
    if isinstance(beats_raw, str):
        beats_raw = json.loads(beats_raw)

    texts: dict[str, str] = {}
    texts["hook"] = script["hook"]

    for i, beat in enumerate(beats_raw, start=1):
        texts[f"beat_{i}"] = f"{beat['fact']} {beat['analogy']}"

    texts["payoff"] = script["payoff"]

    cta = script.get("cta") or ""
    if cta.strip():
        texts["cta"] = cta

    return texts


# ── Agente principal ───────────────────────────────────────────────────────────


def build_storyboard(video_id: UUID) -> dict:
    """Monta storyboard com timestamps precisos baseados nas durações reais do áudio.

    Args:
        video_id: UUID do vídeo em videos.

    Returns:
        Dict com video_id, total_duration e lista de scenes com t0/t1/type/text.
    """
    t0 = time.monotonic()
    conn = _get_conn()
    storyboard: dict = {}

    try:
        script = _fetch_script(conn, video_id)
        texts = _build_texts(script)
        durations = _read_durations(video_id)

        if not durations:
            raise FileNotFoundError(
                f"Nenhum arquivo .mp3 encontrado em {AUDIO_BASE / str(video_id)}"
            )

        log.info(
            "Montando storyboard para vídeo %s — %d segmentos",
            str(video_id)[:8],
            len(durations),
        )

        # Constrói cenas com timestamps cumulativos
        scenes = []
        cursor = 0.0
        for seg_id in SEGMENT_ORDER:
            if seg_id not in durations:
                continue
            if seg_id not in texts:
                continue  # cta omitido se vazio
            duration = durations[seg_id]
            t1 = round(cursor + duration, 3)
            scenes.append(
                {
                    "id": seg_id,
                    "t0": round(cursor, 3),
                    "t1": t1,
                    "type": SCENE_TYPES[seg_id],
                    "text": texts[seg_id],
                }
            )
            log.info(
                "  [%s] %.3fs → %.3fs (%.3fs)",
                seg_id, cursor, t1, duration,
            )
            cursor = t1

        total_duration = round(cursor, 3)
        storyboard = {
            "video_id": str(video_id),
            "total_duration": total_duration,
            "scenes": scenes,
        }

        # Salva em output/storyboards/{video_id}.json
        STORYBOARD_BASE.mkdir(parents=True, exist_ok=True)
        out_path = STORYBOARD_BASE / f"{video_id}.json"
        out_path.write_text(json.dumps(storyboard, ensure_ascii=False, indent=2))

        duration_ms = int((time.monotonic() - t0) * 1000)
        log.info(
            "build_storyboard concluído: %dms | total=%.3fs | %d cenas | %s",
            duration_ms, total_duration, len(scenes), out_path,
        )

        _record_agent_run(conn, video_id, storyboard, duration_ms, "success")
        conn.commit()

        return storyboard

    except Exception as exc:
        conn.rollback()
        duration_ms = int((time.monotonic() - t0) * 1000)
        log.error("build_storyboard falhou: %s", exc)
        try:
            _record_agent_run(conn, video_id, storyboard, duration_ms, "failed", str(exc))
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
        description="Storyboard Director — monta storyboard com timestamps de áudio"
    )
    _parser.add_argument(
        "--video-id",
        metavar="UUID",
        help="UUID do vídeo (opcional; padrão: primeiro com status='scripted' e áudio gerado)",
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
            # Primeiro vídeo scripted com áudio gerado
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
        if _args.video_id:
            print(f"Vídeo não encontrado: {_args.video_id}")
        else:
            print("Nenhum vídeo com status='scripted' encontrado.")
            print("Execute primeiro: uv run python agents/tts.py")
        sys.exit(1)

    _video_id, _title = _row

    # Verifica se há áudio gerado
    _audio_dir = AUDIO_BASE / str(_video_id)
    if not (_audio_dir / "hook.mp3").exists():
        print(f"Áudio não encontrado em {_audio_dir}")
        print("Execute primeiro: uv run python agents/tts.py")
        sys.exit(1)

    print(f"Vídeo:  [{str(_video_id)[:8]}] {_title}")
    print("Iniciando build_storyboard...\n")

    _storyboard = build_storyboard(UUID(str(_video_id)))

    print(f"\n{'─' * 60}")
    print(f"Storyboard: {_storyboard['total_duration']}s total | {len(_storyboard['scenes'])} cenas")
    print()
    print(f"{'ID':<10} {'t0':>7} {'t1':>7} {'dur':>6}  {'type':<16}  texto (50 chars)")
    print(f"{'─'*10} {'─'*7} {'─'*7} {'─'*6}  {'─'*16}  {'─'*50}")
    for _scene in _storyboard["scenes"]:
        _dur = round(_scene["t1"] - _scene["t0"], 3)
        _text_preview = _scene["text"][:50].replace("\n", " ")
        print(
            f"{_scene['id']:<10} {_scene['t0']:>7.3f} {_scene['t1']:>7.3f} {_dur:>6.3f}"
            f"  {_scene['type']:<16}  {_text_preview}"
        )
    print(f"\nSalvo em: output/storyboards/{str(_video_id)}/")
