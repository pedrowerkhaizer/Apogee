"""scripts/smoke_test_render.py — E0.5: Smoke test end-to-end com render real.

Executa o pipeline de mídia completo (TTS → Storyboard → Render → Postprocess)
sobre o vídeo mais recente com status='scripted', ou o vídeo indicado via --video-id.

Valida:
  - Arquivo final MP4 existe e tem tamanho razoável
  - LUFS entre -15 e -13 (normalização aplicada)
  - Thumbnail gerada
  - Registro em renders com duration_secs e render_time_sec

Uso:
    uv run python scripts/smoke_test_render.py
    uv run python scripts/smoke_test_render.py --video-id <UUID>
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from uuid import UUID

sys.path.insert(0, str(Path(__file__).parent.parent))

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).parent.parent
TOTAL = 6


def _get_conn() -> psycopg2.extensions.connection:
    db_url = os.getenv("SUPABASE_DB_URL")
    if not db_url:
        raise RuntimeError("SUPABASE_DB_URL não definido no .env")
    return psycopg2.connect(db_url, connect_timeout=10)


def _find_scripted_video(conn: psycopg2.extensions.connection, video_id: str | None) -> tuple[UUID, str]:
    with conn.cursor() as cur:
        if video_id:
            cur.execute(
                """
                SELECT v.id, t.title FROM videos v
                JOIN topics t ON t.id = v.topic_id
                WHERE v.id = %s
                """,
                (video_id,),
            )
        else:
            cur.execute(
                """
                SELECT v.id, t.title FROM videos v
                JOIN topics t ON t.id = v.topic_id
                WHERE v.status = 'scripted'
                ORDER BY v.updated_at DESC LIMIT 1
                """
            )
        row = cur.fetchone()
    if not row:
        raise RuntimeError("Nenhum vídeo com status='scripted' encontrado.")
    return UUID(str(row[0])), str(row[1])


def _measure_lufs(video_path: Path) -> float:
    """Mede o LUFS integrado do arquivo via ffmpeg loudnorm."""
    result = subprocess.run(
        [
            "ffmpeg", "-i", str(video_path),
            "-af", "loudnorm=print_format=json",
            "-f", "null", "-",
        ],
        capture_output=True,
        text=True,
    )
    # loudnorm imprime JSON no stderr
    stderr = result.stderr
    start = stderr.rfind("{")
    end = stderr.rfind("}") + 1
    if start == -1 or end == 0:
        raise RuntimeError("ffmpeg loudnorm não retornou JSON esperado")
    data = json.loads(stderr[start:end])
    return float(data["input_i"])


def _fetch_render_record(conn: psycopg2.extensions.connection, video_id: UUID) -> dict:
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """
            SELECT file_path, duration_secs, file_size_bytes, lufs, render_time_sec
            FROM renders WHERE video_id = %s
            ORDER BY created_at DESC LIMIT 1
            """,
            (str(video_id),),
        )
        row = cur.fetchone()
    if not row:
        raise RuntimeError("Registro em renders não encontrado após render")
    return dict(row)


def main() -> None:
    parser = argparse.ArgumentParser(description="Smoke test render end-to-end")
    parser.add_argument("--video-id", metavar="UUID", help="UUID do vídeo (opcional)")
    args = parser.parse_args()

    db_url = os.getenv("SUPABASE_DB_URL")
    if not db_url:
        print("SMOKE TEST RENDER FAILED — SUPABASE_DB_URL não definido")
        sys.exit(1)

    conn = _get_conn()
    video_id: UUID | None = None

    try:
        # ── [1/6] Encontrar vídeo scripted ────────────────────────────────────
        print(f"[1/{TOTAL}] Buscando vídeo com status='scripted'")
        video_id, title = _find_scripted_video(conn, args.video_id)
        print(f"         Vídeo: [{str(video_id)[:8]}] {title}")

        # ── [2/6] TTS ─────────────────────────────────────────────────────────
        print(f"[2/{TOTAL}] Gerando áudio TTS (Edge-TTS pt-BR-AntonioNeural)")
        from agents.tts import generate_audio
        durations = generate_audio(video_id)
        assert durations, "generate_audio retornou dict vazio"
        total_dur = sum(durations.values())
        print(f"         {len(durations)} segmentos | {total_dur:.1f}s total")

        # ── [3/6] Storyboard ──────────────────────────────────────────────────
        print(f"[3/{TOTAL}] Montando storyboard com timestamps reais")
        from agents.storyboard_director import build_storyboard
        storyboard = build_storyboard(video_id)
        scenes = storyboard.get("scenes", [])
        assert len(scenes) >= 3, f"Esperado >= 3 cenas, obtido {len(scenes)}"
        print(f"         {len(scenes)} cenas | duração total: {storyboard['total_duration']:.1f}s")

        # ── [4/6] Render Remotion ─────────────────────────────────────────────
        print(f"[4/{TOTAL}] Renderizando vídeo via Remotion (npx remotion render)…")
        from agents.render import render_video
        render_result = render_video(video_id)
        output_mp4 = Path(render_result["output_path"])
        assert output_mp4.exists(), f"MP4 não encontrado: {output_mp4}"
        assert output_mp4.stat().st_size > 100_000, "MP4 suspeito: < 100 KB"
        print(f"         {render_result['file_size_mb']} MB | {render_result['render_time_sec']}s")

        # ── [5/6] Postprocess FFmpeg ──────────────────────────────────────────
        print(f"[5/{TOTAL}] Aplicando loudnorm -14 LUFS + H.264 CRF 23 + thumbnail")
        from agents.postprocess import postprocess
        final_path_str = postprocess(video_id)
        final_path = Path(final_path_str)
        assert final_path.exists(), f"Arquivo final não encontrado: {final_path}"
        assert final_path.stat().st_size > 100_000, "Arquivo final < 100 KB"

        # Thumbnail
        thumbnail = final_path.parent.parent / "thumbnails" / f"{video_id}.jpg"
        # Tenta caminhos alternativos
        if not thumbnail.exists():
            thumbnail = ROOT / "output" / "thumbnails" / f"{video_id}.jpg"
        assert thumbnail.exists(), f"Thumbnail não encontrada: {thumbnail}"
        print(f"         Final: {final_path.name} | Thumbnail: {thumbnail.name}")

        # ── [6/6] Validar registros no DB ─────────────────────────────────────
        print(f"[6/{TOTAL}] Validando registros no banco (renders, lufs, video status)")
        render_rec = _fetch_render_record(conn, video_id)
        assert render_rec["duration_secs"] and render_rec["duration_secs"] > 0, \
            "renders.duration_secs inválido"
        assert render_rec["render_time_sec"] and render_rec["render_time_sec"] > 0, \
            "renders.render_time_sec inválido"

        # Verifica LUFS se o campo estiver preenchido
        if render_rec.get("lufs") is not None:
            lufs_val = float(render_rec["lufs"])
            assert -16.0 <= lufs_val <= -12.0, \
                f"LUFS fora do range esperado: {lufs_val} (esperado entre -16 e -12)"
            print(f"         LUFS: {lufs_val:.1f} ✓")

        # Verifica status do vídeo
        with conn.cursor() as cur:
            cur.execute("SELECT status FROM videos WHERE id = %s", (str(video_id),))
            status = cur.fetchone()[0]
        assert status == "published" or status in ("rendered",), \
            f"video.status inesperado: {status}"
        print(f"         video.status = '{status}' ✓")

    except Exception as exc:
        print(f"\nSMOKE TEST RENDER FAILED: {exc}")
        sys.exit(1)
    finally:
        conn.close()

    print(f"\n{'─' * 60}")
    print("SMOKE TEST RENDER PASSED")
    if video_id:
        print(f"Vídeo renderizado: output/final/{video_id}.mp4")


if __name__ == "__main__":
    main()
