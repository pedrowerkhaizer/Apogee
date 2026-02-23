"""agents/topic_miner.py — Topic Miner agent.

Gera 20 candidatos de tópico via Claude API, filtra por similaridade
semântica (all-MiniLM-L6-v2 + pgvector cosine) e persiste os aprovados
com status='pending'.

Uso manual:
    uv run python agents/topic_miner.py
"""

from __future__ import annotations

import logging
import os
import time
from uuid import UUID

import anthropic
import numpy as np
import psycopg2
import psycopg2.extras
from dotenv import load_dotenv
from langsmith import traceable
from pgvector.psycopg2 import register_vector
from sentence_transformers import SentenceTransformer

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# ── Constantes ─────────────────────────────────────────────────────────────────

AGENT_NAME = "topic_miner"
CLAUDE_MODEL = "claude-sonnet-4-6"
CANDIDATE_COUNT = 20
APPROVED_LOOKBACK = 50
SIMILARITY_THRESHOLD = 0.75

INPUT_COST_PER_TOK = 3.0 / 1_000_000   # $3 por MTok input
OUTPUT_COST_PER_TOK = 15.0 / 1_000_000  # $15 por MTok output

# ── Sentence Transformer (lazy, carregado uma vez) ─────────────────────────────

_embedder: SentenceTransformer | None = None


def _get_embedder() -> SentenceTransformer:
    global _embedder
    if _embedder is None:
        log.info("Carregando modelo all-MiniLM-L6-v2 (CPU)...")
        _embedder = SentenceTransformer("all-MiniLM-L6-v2", device="cpu")
    return _embedder


# ── Helpers de banco ───────────────────────────────────────────────────────────


def _get_conn() -> psycopg2.extensions.connection:
    db_url = os.getenv("SUPABASE_DB_URL")
    if not db_url:
        raise RuntimeError("SUPABASE_DB_URL não definido no .env")
    conn = psycopg2.connect(db_url, connect_timeout=10)
    register_vector(conn)
    return conn


def _fetch_channel(conn: psycopg2.extensions.connection, channel_id: UUID) -> dict:
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """
            SELECT channel_name, niche, tone, target_audience, language
            FROM   channel_config
            WHERE  id = %s
            """,
            (str(channel_id),),
        )
        row = cur.fetchone()
    if not row:
        raise ValueError(f"Canal não encontrado: {channel_id}")
    return dict(row)


def _max_similarity(
    conn: psycopg2.extensions.connection,
    channel_id: UUID,
    embedding: np.ndarray,
) -> float | None:
    """Cosine similarity máxima entre embedding e os últimos N approved topics."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT MAX(1.0 - (embedding <=> %s)) AS max_sim
            FROM (
                SELECT embedding
                FROM   topics
                WHERE  channel_id = %s
                  AND  status     = 'approved'
                  AND  embedding  IS NOT NULL
                ORDER  BY created_at DESC
                LIMIT  %s
            ) sub
            """,
            (embedding, str(channel_id), APPROVED_LOOKBACK),
        )
        row = cur.fetchone()
    if row and row[0] is not None:
        return float(row[0])
    return None


def _insert_topic(
    conn: psycopg2.extensions.connection,
    channel_id: UUID,
    candidate: dict,
    embedding: np.ndarray,
    similarity_score: float | None,
) -> str:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO topics
                (channel_id, title, rationale, status, embedding, similarity_score)
            VALUES (%s, %s, %s, 'pending', %s, %s)
            RETURNING id
            """,
            (
                str(channel_id),
                candidate["title"],
                candidate.get("rationale"),
                embedding,
                similarity_score,
            ),
        )
        return str(cur.fetchone()[0])


def _record_agent_run(
    conn: psycopg2.extensions.connection,
    channel_id: UUID,
    response: anthropic.types.Message | None,
    saved: list[dict],
    duration_ms: int,
    status: str,
    error_message: str | None = None,
) -> None:
    tokens_input = response.usage.input_tokens if response else 0
    tokens_output = response.usage.output_tokens if response else 0
    cost_usd = tokens_input * INPUT_COST_PER_TOK + tokens_output * OUTPUT_COST_PER_TOK

    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO agent_runs
                (agent_name, status, input_json, output_json,
                 tokens_input, tokens_output, cost_usd, duration_ms, error_message)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                AGENT_NAME,
                status,
                psycopg2.extras.Json(
                    {"channel_id": str(channel_id), "candidate_count": CANDIDATE_COUNT}
                ),
                psycopg2.extras.Json(
                    {
                        "saved": len(saved),
                        "rejected": CANDIDATE_COUNT - len(saved),
                        "topics": saved,
                    }
                ),
                tokens_input,
                tokens_output,
                round(cost_usd, 6),
                duration_ms,
                error_message,
            ),
        )


# ── Claude API ─────────────────────────────────────────────────────────────────


def _call_claude(
    client: anthropic.Anthropic, channel: dict
) -> anthropic.types.Message:
    system = (
        f"Você é um estrategista de conteúdo para o canal YouTube '{channel['channel_name']}'.\n"
        f"Nicho: {channel['niche']}\n"
        f"Tom: {channel['tone']}\n"
        f"Público-alvo: {channel['target_audience']}\n\n"
        "Gere tópicos com fatos científicos verificáveis, dados surpreendentes ou contraintuitivos. "
        "Cada tópico deve ter potencial para um gancho de plot twist que prenda a atenção "
        "nos primeiros 30 segundos do vídeo."
    )
    user = (
        f"Gere exatamente {CANDIDATE_COUNT} candidatos de tópico para vídeos do YouTube. "
        "Foco em curiosidades científicas verificáveis com dados contraintuitivos ou surpreendentes. "
        "Todos os títulos devem estar em português do Brasil (pt-BR). "
        "Para cada tópico, forneça um título envolvente e uma justificativa (rationale) "
        "explicando o potencial de engajamento e o ângulo contraintuitivo."
    )

    return client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=4096,
        system=system,
        tools=[
            {
                "name": "submit_topics",
                "description": "Submete a lista de candidatos de tópico gerados",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "topics": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "title": {
                                        "type": "string",
                                        "description": "Título do tópico em pt-BR",
                                    },
                                    "rationale": {
                                        "type": "string",
                                        "description": "Por que esse tópico tem potencial de engajamento",
                                    },
                                },
                                "required": ["title", "rationale"],
                            },
                            "minItems": CANDIDATE_COUNT,
                            "maxItems": CANDIDATE_COUNT,
                        }
                    },
                    "required": ["topics"],
                },
            }
        ],
        tool_choice={"type": "tool", "name": "submit_topics"},
        messages=[{"role": "user", "content": user}],
    )


def _parse_candidates(response: anthropic.types.Message) -> list[dict]:
    for block in response.content:
        if block.type == "tool_use" and block.name == "submit_topics":
            return block.input["topics"]
    raise ValueError("Claude não retornou tool_use com 'submit_topics'")


# ── Agente principal ───────────────────────────────────────────────────────────


@traceable(name=AGENT_NAME)
def mine_topics(channel_id: UUID) -> list[dict]:
    """Gera e persiste candidatos de tópico para o canal.

    Args:
        channel_id: UUID do canal em channel_config.

    Returns:
        Lista de dicts com {id, title, similarity_score} dos tópicos inseridos
        com status='pending'.
    """
    t0 = time.monotonic()
    client = anthropic.Anthropic()
    conn = _get_conn()

    try:
        # 1. Contexto do canal
        channel = _fetch_channel(conn, channel_id)
        log.info("Minerando tópicos para canal '%s'...", channel["channel_name"])

        # 2. Gera candidatos via Claude
        log.info("Chamando %s...", CLAUDE_MODEL)
        response = _call_claude(client, channel)
        candidates = _parse_candidates(response)
        log.info(
            "Claude gerou %d candidatos  (%d tokens in / %d tokens out)",
            len(candidates),
            response.usage.input_tokens,
            response.usage.output_tokens,
        )

        # 3. Embeddings + deduplicação + persistência
        embedder = _get_embedder()
        saved: list[dict] = []

        for candidate in candidates:
            emb: np.ndarray = embedder.encode(candidate["title"])
            max_sim = _max_similarity(conn, channel_id, emb)

            if max_sim is not None and max_sim > SIMILARITY_THRESHOLD:
                log.info("  ✗ Rejeitado (sim=%.3f): %s", max_sim, candidate["title"])
                continue

            topic_id = _insert_topic(conn, channel_id, candidate, emb, max_sim)
            saved.append(
                {
                    "id": topic_id,
                    "title": candidate["title"],
                    "similarity_score": max_sim,
                }
            )
            log.info("  ✓ Salvo: %s", candidate["title"])

        conn.commit()

        # 4. Registra execução em agent_runs
        duration_ms = int((time.monotonic() - t0) * 1000)
        cost_usd = (
            response.usage.input_tokens * INPUT_COST_PER_TOK
            + response.usage.output_tokens * OUTPUT_COST_PER_TOK
        )
        _record_agent_run(conn, channel_id, response, saved, duration_ms, "success")
        conn.commit()

        log.info(
            "mine_topics concluído: %d/%d salvos em %dms  (custo estimado $%.4f)",
            len(saved),
            CANDIDATE_COUNT,
            duration_ms,
            cost_usd,
        )
        return saved

    except Exception as exc:
        conn.rollback()
        duration_ms = int((time.monotonic() - t0) * 1000)
        log.error("mine_topics falhou: %s", exc)
        try:
            _record_agent_run(conn, channel_id, None, [], duration_ms, "failed", str(exc))
            conn.commit()
        except Exception:
            pass
        raise

    finally:
        conn.close()


# ── Execução manual ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    from pathlib import Path

    # Garante que a raiz do projeto está em sys.path quando rodado como script
    sys.path.insert(0, str(Path(__file__).parent.parent))

    _db_url = os.getenv("SUPABASE_DB_URL")
    if not _db_url:
        print("SUPABASE_DB_URL não definido no .env")
        sys.exit(1)

    # Busca o channel_id do canal "Apogee Engine" (inserido pelo seed)
    _conn = psycopg2.connect(_db_url, connect_timeout=10)
    with _conn.cursor() as _cur:
        _cur.execute(
            "SELECT id FROM channel_config WHERE channel_name = 'Apogee Engine'"
        )
        _row = _cur.fetchone()
    _conn.close()

    if not _row:
        print("Canal 'Apogee Engine' não encontrado. Execute: uv run python scripts/seed_channel.py")
        sys.exit(1)

    _channel_id = UUID(str(_row[0]))
    print(f"Canal encontrado: {_channel_id}")
    print(f"Iniciando mine_topics...\n")

    _topics = mine_topics(_channel_id)

    print(f"\n{'─'*60}")
    print(f"{len(_topics)} tópicos salvos com status='pending':")
    for _t in _topics:
        sim = f"sim={_t['similarity_score']:.3f}" if _t["similarity_score"] is not None else "sem histórico"
        print(f"  [{_t['id'][:8]}] ({sim}) {_t['title']}")
