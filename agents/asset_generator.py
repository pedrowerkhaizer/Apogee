"""agents/asset_generator.py — Gerador de assets visuais por claim.

Detecta claims com dados quantitativos ou comparações e gera gráficos PNG
com matplotlib. Persiste na tabela assets com checksum SHA256 para evitar reuso.

Uso manual:
    uv run python agents/asset_generator.py --video-id <UUID>
"""

from __future__ import annotations

import sys
from pathlib import Path

# Garante que a raiz do projeto está em sys.path ao rodar como script
sys.path.insert(0, str(Path(__file__).parent.parent))

import hashlib
import logging
import os
import re
import time
from uuid import UUID

import textwrap

import matplotlib
matplotlib.use("Agg")  # backend sem display
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
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

AGENT_NAME = "asset_generator"
ROOT = Path(__file__).parent.parent
OUTPUT_ASSETS = ROOT / "output" / "assets"

# Padrões para detecção de tipo de asset
_RE_NUMERIC = re.compile(
    r"\b\d[\d\.,]*\s*(?:%|mil|milhão|milhões|bilhão|bilhões|x|k|m|b|kg|g|km|m|cm|s|ms)?\b",
    re.IGNORECASE,
)
_RE_COMPARISON = re.compile(
    r"\b(vs\.?|versus|contra|comparado|maior\s+que|menor\s+que|mais\s+(?:do\s+)?que"
    r"|menos\s+(?:do\s+)?que|diferença|supera|superam)\b",
    re.IGNORECASE,
)

# Paleta dark
_BG_COLOR = "#0f0f1a"
_BAR_COLORS = ["#4a90d9", "#7b5ea7", "#e74c3c", "#2ecc71", "#f39c12"]
_LEFT_COLOR = "#4a90d9"
_RIGHT_COLOR = "#e74c3c"
_TEXT_COLOR = "#e8e8f0"


# ── Helpers de banco ───────────────────────────────────────────────────────────


def _get_conn() -> psycopg2.extensions.connection:
    db_url = os.getenv("SUPABASE_DB_URL")
    if not db_url:
        raise RuntimeError("SUPABASE_DB_URL não definido no .env")
    return psycopg2.connect(db_url, connect_timeout=10)


def _fetch_claims(conn: psycopg2.extensions.connection, video_id: UUID) -> list[dict]:
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """
            SELECT id, claim_text, source_url, risk_score
            FROM   claims
            WHERE  video_id = %s
            ORDER  BY created_at
            """,
            (str(video_id),),
        )
        return [dict(r) for r in cur.fetchall()]


def _checksum_exists(conn: psycopg2.extensions.connection, checksum: str) -> str | None:
    """Retorna asset_id se já existe asset com esse checksum, senão None."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id FROM assets WHERE checksum = %s LIMIT 1",
            (checksum,),
        )
        row = cur.fetchone()
    return str(row[0]) if row else None


def _insert_asset(
    conn: psycopg2.extensions.connection,
    video_id: UUID,
    asset_type: str,
    file_path: str,
    checksum: str,
    metadata: dict,
) -> str:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO assets (video_id, asset_type, origin, file_path, checksum, metadata)
            VALUES (%s, %s, 'generated', %s, %s, %s)
            RETURNING id
            """,
            (
                str(video_id),
                asset_type,
                file_path,
                checksum,
                psycopg2.extras.Json(metadata),
            ),
        )
        return str(cur.fetchone()[0])


def _record_agent_run(
    conn: psycopg2.extensions.connection,
    video_id: UUID,
    assets_count: int,
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
                psycopg2.extras.Json({"assets_generated": assets_count}),
                duration_ms,
                error_message,
            ),
        )


# ── Detecção de tipo ────────────────────────────────────────────────────────────


def _detect_type(claim_text: str) -> str | None:
    """Retorna 'stat_card', 'comparison', ou None se não aplicável."""
    if _RE_COMPARISON.search(claim_text):
        return "comparison"
    if _RE_NUMERIC.search(claim_text):
        return "stat_card"
    return None


# ── Geração de gráficos ────────────────────────────────────────────────────────

def _truncate(text: str, max_len: int = 60) -> str:
    return text if len(text) <= max_len else text[:max_len - 1] + "…"


# Palavras que não servem como unidade (preposições, artigos, conjunções PT-BR)
_STOPWORDS_UNIT = {
    "de", "da", "do", "das", "dos", "a", "o", "as", "os",
    "um", "uma", "e", "em", "no", "na", "por", "que", "se",
    "ao", "à", "com", "mas", "ou", "foi", "é", "são",
}


def _extract_primary_stat(claim_text: str) -> str:
    """Extrai o dado numérico principal do claim como string de exibição.

    Exemplo: "20 watts", "175 bilhões", "8,96 MB/s"
    Retorna o primeiro número significativo com sua unidade (se houver).
    Ignora números dentro de tokens compostos (GPT-3, COVID-19, etc.).
    """
    # (?<![a-zA-ZÀ-ú\-]) → não pega número precedido por letra ou hífen (ex: GPT-3)
    num_re = re.compile(r'(?<![a-zA-ZÀ-ú\-])(\d[\d\.,]*)\s*([a-zA-ZÀ-ú%/]{1,15})?')
    for m in num_re.finditer(claim_text):
        raw_num = m.group(1).rstrip(".,")   # remove vírgula/ponto final (ex: "3,")
        unit_raw = (m.group(2) or "").strip()

        # Valida que é um número positivo
        clean = raw_num.replace(",", ".")
        if clean.count(".") > 1:
            clean = clean.replace(".", "", clean.count(".") - 1)
        try:
            value = float(clean)
        except ValueError:
            continue
        if value <= 0:
            continue

        # Aceita a unidade apenas se não for stopword
        unit = unit_raw if unit_raw.lower() not in _STOPWORDS_UNIT else ""
        return f"{raw_num} {unit}".strip() if unit else raw_num

    return "?"


def _stat_fontsize(text: str) -> int:
    """Tamanho de fonte adaptivo para o stat principal."""
    n = len(text)
    if n <= 6:
        return 72
    if n <= 12:
        return 56
    if n <= 18:
        return 40
    return 30


def _generate_stat_card(claim_text: str, output_path: Path) -> None:
    """Gera card visual com o dado numérico principal + claim completo.

    Layout:
      - Topo: stat em destaque (número + unidade, fonte grande)
      - Linha divisória
      - Corpo: claim completo quebrado em múltiplas linhas
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    stat = _extract_primary_stat(claim_text)
    body = textwrap.fill(claim_text, width=70)

    fig, ax = plt.subplots(figsize=(11.25, 6.25), dpi=96)
    fig.patch.set_facecolor(_BG_COLOR)
    ax.set_facecolor(_BG_COLOR)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    # Stat principal — centro-alto
    ax.text(
        0.5, 0.70,
        stat,
        ha="center", va="center",
        transform=ax.transAxes,
        fontsize=_stat_fontsize(stat),
        fontweight="bold",
        color=_BAR_COLORS[0],
    )

    # Linha divisória
    ax.plot(
        [0.10, 0.90], [0.52, 0.52],
        transform=ax.transAxes,
        color=_BAR_COLORS[0],
        alpha=0.40,
        linewidth=1.5,
    )

    # Claim completo — abaixo da linha
    ax.text(
        0.5, 0.30,
        body,
        ha="center", va="center",
        transform=ax.transAxes,
        fontsize=11,
        color=_TEXT_COLOR,
        multialignment="center",
        linespacing=1.5,
    )

    plt.tight_layout(pad=1.5)
    fig.savefig(output_path, facecolor=_BG_COLOR, bbox_inches="tight", dpi=96)
    plt.close(fig)
    log.info("stat_card salvo: %s", output_path.name)


def _split_comparison(claim_text: str) -> tuple[str, str]:
    """Divide o claim ao redor do keyword de comparação."""
    match = _RE_COMPARISON.search(claim_text)
    if match:
        left = claim_text[: match.start()].strip(" .,;:")
        right = claim_text[match.end() :].strip(" .,;:")
        return (left or claim_text, right or claim_text)
    return (claim_text, claim_text)


def _generate_comparison(claim_text: str, output_path: Path) -> None:
    """Gera diagrama de comparação lado a lado com texto quebrado dentro das caixas."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    left_text, right_text = _split_comparison(claim_text)

    fig, axes = plt.subplots(1, 2, figsize=(11.25, 6.25), dpi=96)
    fig.patch.set_facecolor(_BG_COLOR)

    for ax, text, color, side_label in [
        (axes[0], left_text, _LEFT_COLOR, "A"),
        (axes[1], right_text, _RIGHT_COLOR, "B"),
    ]:
        ax.set_facecolor(_BG_COLOR)

        # Caixa de fundo
        rect = mpatches.FancyBboxPatch(
            (0.05, 0.10), 0.90, 0.80,
            boxstyle="round,pad=0.02",
            facecolor=color,
            alpha=0.20,
            edgecolor=color,
            linewidth=2,
            transform=ax.transAxes,
        )
        ax.add_patch(rect)

        # Letra identificadora (dentro da caixa, topo)
        ax.text(
            0.50, 0.82,
            side_label,
            ha="center", va="center",
            transform=ax.transAxes,
            fontsize=32,
            fontweight="bold",
            color=color,
        )

        # Texto quebrado manualmente com textwrap para caber dentro da caixa
        wrapped = textwrap.fill(text, width=28)
        ax.text(
            0.50, 0.46,
            wrapped,
            ha="center", va="center",
            transform=ax.transAxes,
            fontsize=10,
            color=_TEXT_COLOR,
            multialignment="center",
            linespacing=1.4,
            clip_on=True,
        )

        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.axis("off")

    fig.suptitle(
        _truncate(claim_text, 90),
        color=_TEXT_COLOR,
        fontsize=10,
        y=0.98,
    )

    plt.tight_layout(pad=1.2)
    fig.savefig(output_path, facecolor=_BG_COLOR, bbox_inches="tight", dpi=96)
    plt.close(fig)
    log.info("comparison salvo: %s", output_path.name)


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


# ── Agente principal ───────────────────────────────────────────────────────────


@traceable(name=AGENT_NAME)
def generate_assets(video_id: UUID) -> list[dict]:
    """Gera assets visuais (PNG) para os claims de um vídeo.

    Args:
        video_id: UUID do vídeo em videos.

    Returns:
        Lista de dicts com asset_id, claim_id, asset_type, file_path,
        checksum, reused.
    """
    t0 = time.monotonic()
    conn = _get_conn()
    results: list[dict] = []

    try:
        claims = _fetch_claims(conn, video_id)
        log.info("Claims encontrados: %d para video_id=%s", len(claims), str(video_id)[:8])

        for n, claim in enumerate(claims, start=1):
            claim_text: str = claim["claim_text"]
            asset_type = _detect_type(claim_text)

            if asset_type is None:
                log.debug("Claim %d sem asset detectável: %.60s", n, claim_text)
                continue

            out_dir = OUTPUT_ASSETS / str(video_id)
            out_path = out_dir / f"asset_{n}.png"

            # Gera gráfico
            if asset_type == "stat_card":
                _generate_stat_card(claim_text, out_path)
            else:
                _generate_comparison(claim_text, out_path)

            # Checksum e detecção de reuso
            checksum = _sha256(out_path)
            existing_id = _checksum_exists(conn, checksum)

            if existing_id:
                log.info("Asset reusado (checksum já existe): %s", existing_id)
                results.append(
                    {
                        "asset_id": existing_id,
                        "claim_id": str(claim["id"]),
                        "asset_type": asset_type,
                        "file_path": str(out_path),
                        "checksum": checksum,
                        "reused": True,
                    }
                )
                continue

            # Persiste no banco
            asset_id = _insert_asset(
                conn,
                video_id,
                asset_type,
                str(out_path),
                checksum,
                {
                    "claim_id": str(claim["id"]),
                    "claim_text": claim_text[:200],
                    "n": n,
                },
            )

            results.append(
                {
                    "asset_id": asset_id,
                    "claim_id": str(claim["id"]),
                    "asset_type": asset_type,
                    "file_path": str(out_path),
                    "checksum": checksum,
                    "reused": False,
                }
            )
            log.info("Asset %d persistido: %s [%s]", n, asset_id[:8], asset_type)

        duration_ms = int((time.monotonic() - t0) * 1000)
        _record_agent_run(conn, video_id, len(results), duration_ms, "success")
        conn.commit()

        log.info(
            "generate_assets concluído: %d assets em %.1fs",
            len(results),
            time.monotonic() - t0,
        )
        return results

    except Exception as exc:
        conn.rollback()
        duration_ms = int((time.monotonic() - t0) * 1000)
        log.error("generate_assets falhou: %s", exc)
        try:
            _record_agent_run(conn, video_id, len(results), duration_ms, "failed", str(exc))
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
        description="Asset Generator — gera gráficos PNG por claim de um vídeo"
    )
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
                WHERE  v.status IN ('scripted', 'rendered', 'published')
                ORDER  BY v.updated_at DESC
                LIMIT  1
                """
            )
        _row = _cur.fetchone()
    _conn.close()

    if not _row:
        if _args.video_id:
            print(f"Vídeo não encontrado: {_args.video_id}")
        else:
            print("Nenhum vídeo com status scripted/rendered/published encontrado.")
        sys.exit(1)

    _video_id, _title = _row
    print(f"Vídeo:  [{str(_video_id)[:8]}] {_title}")
    print("Gerando assets...\n")

    _assets = generate_assets(UUID(str(_video_id)))

    print(f"\n{'─' * 60}")
    print(f"Assets gerados: {len(_assets)}")
    for a in _assets:
        reused_tag = " [reusado]" if a["reused"] else ""
        print(f"  [{a['asset_type']:12s}] {Path(a['file_path']).name}{reused_tag}")
    print(f"Diretório:  output/assets/{_video_id}/")
