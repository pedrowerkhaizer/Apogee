"""agents/scriptwriter.py — Scriptwriter agent.

Para um dado tópico, gera um roteiro estruturado (hook + beats + payoff + cta)
usando Claude API, verifica similaridade com scripts existentes via pgvector
e persiste o resultado no banco.

Uso manual:
    uv run python agents/scriptwriter.py
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

import anthropic
import numpy as np
import psycopg2
import psycopg2.extras
from dotenv import load_dotenv
from langsmith import traceable
from pgvector.psycopg2 import register_vector
from sentence_transformers import SentenceTransformer

from models import Script, ScriptBeat

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# ── Constantes ─────────────────────────────────────────────────────────────────

AGENT_NAME = "scriptwriter"
CLAUDE_MODEL = "claude-sonnet-4-6"
SIMILARITY_THRESHOLD = 0.80
LOOKBACK = 50

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


def _fetch_topic_and_video(
    conn: psycopg2.extensions.connection, topic_id: UUID
) -> dict:
    """Retorna dados do tópico + canal + video_id do rascunho associado."""
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """
            SELECT t.id          AS topic_id,
                   t.title,
                   t.rationale,
                   t.channel_id,
                   c.channel_name,
                   c.niche,
                   c.tone,
                   c.target_audience,
                   v.id          AS video_id
            FROM   topics t
            JOIN   channel_config c ON c.id = t.channel_id
            JOIN   videos v         ON v.topic_id = t.id
            WHERE  t.id = %s
              AND  v.status = 'draft'
            ORDER  BY v.created_at ASC
            LIMIT  1
            """,
            (str(topic_id),),
        )
        row = cur.fetchone()
    if not row:
        raise ValueError(
            f"Tópico não encontrado ou sem vídeo draft: {topic_id}"
        )
    return dict(row)


def _fetch_claims(
    conn: psycopg2.extensions.connection, video_id: str
) -> list[dict]:
    """Retorna claims do vídeo ordenados por risk_score ASC (melhores primeiro)."""
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """
            SELECT claim_text, source_url, risk_score
            FROM   claims
            WHERE  video_id = %s
            ORDER  BY risk_score ASC
            """,
            (video_id,),
        )
        return [dict(r) for r in cur.fetchall()]


def _max_similarity(
    conn: psycopg2.extensions.connection,
    channel_id: UUID,
    embedding: np.ndarray,
) -> float | None:
    """Cosine similarity máxima entre embedding e os últimos N scripts do canal."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT MAX(1.0 - (s.embedding <=> %s)) AS max_sim
            FROM (
                SELECT s.embedding
                FROM   scripts s
                JOIN   videos  v ON v.id = s.video_id
                WHERE  v.channel_id = %s
                  AND  s.embedding  IS NOT NULL
                ORDER  BY s.created_at DESC
                LIMIT  %s
            ) s
            """,
            (embedding, str(channel_id), LOOKBACK),
        )
        row = cur.fetchone()
    if row and row[0] is not None:
        return float(row[0])
    return None


def _insert_script(
    conn: psycopg2.extensions.connection,
    video_id: str,
    script: Script,
    embedding: np.ndarray,
    similarity_score: float | None,
) -> str:
    beats_json = json.dumps([b.model_dump() for b in script.beats])
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO scripts
                (video_id, hook, beats, payoff, cta,
                 embedding, similarity_score, version)
            VALUES (%s, %s, %s::jsonb, %s, %s, %s, %s, 1)
            RETURNING id
            """,
            (
                video_id,
                script.hook,
                beats_json,
                script.payoff,
                script.cta,
                embedding,
                similarity_score,
            ),
        )
        return str(cur.fetchone()[0])


def _update_video_status(
    conn: psycopg2.extensions.connection, video_id: str
) -> None:
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE videos SET status = 'scripted', updated_at = NOW() WHERE id = %s",
            (video_id,),
        )


def _record_agent_run(
    conn: psycopg2.extensions.connection,
    topic_id: UUID,
    video_id: str | None,
    response: anthropic.types.Message | None,
    script: Script | None,
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
                (agent_name, topic_id, video_id, status,
                 input_json, output_json,
                 tokens_input, tokens_output, cost_usd, duration_ms, error_message)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                AGENT_NAME,
                str(topic_id),
                video_id,
                status,
                psycopg2.extras.Json({"topic_id": str(topic_id)}),
                psycopg2.extras.Json(
                    {"script": script.model_dump() if script else None}
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
    client: anthropic.Anthropic,
    topic: dict,
    claims: list[dict],
) -> anthropic.types.Message:
    claims_text = "\n".join(
        f"- {c['claim_text']}"
        + (f" (fonte: {c['source_url']})" if c.get("source_url") else "")
        for c in claims
    )

    system = (
        f"Você é um roteirista especialista em vídeos curtos educativos para YouTube.\n"
        f"Canal: {topic['channel_name']}\n"
        f"Nicho: {topic['niche']}\n"
        f"Tom: {topic['tone']}\n"
        f"Público-alvo: {topic['target_audience']}\n\n"
        "Crie roteiros com ritmo dinâmico, fatos surpreendentes e analogias visuais originais.\n"
        "O roteiro deve ser direto, sem introduções longas, com um gancho que prenda nos primeiros 5 segundos."
    )

    user = (
        f"Tópico: {topic['title']}\n"
        f"Contexto: {topic.get('rationale', '')}\n\n"
        f"Claims verificados:\n{claims_text}\n\n"
        "Gere um roteiro completo com:\n"
        "- hook: 1–2 frases de até 8 palavras — pergunta ou afirmação contraintuitiva que prende imediatamente\n"
        "- beats: exatamente 3 blocos, cada um com 1 fato concreto dos claims + 1 analogia visual original e inesperada\n"
        "- payoff: conclusão que fecha o loop do hook e surpreende com uma reflexão final\n"
        "- cta: opcional, máximo 1 frase. NÃO use variações de 'não esqueça de se inscrever'. "
        "Deixe como string vazia se não for natural ao tópico.\n\n"
        "Todos os textos em português do Brasil (pt-BR)."
    )

    return client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=1024,
        system=system,
        tools=[
            {
                "name": "submit_script",
                "description": "Submete o roteiro estruturado do vídeo",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "hook": {
                            "type": "string",
                            "description": (
                                "1–2 frases, até 8 palavras. "
                                "Pergunta ou afirmação contraintuitiva que prende nos primeiros 5 segundos."
                            ),
                        },
                        "beats": {
                            "type": "array",
                            "minItems": 3,
                            "maxItems": 3,
                            "items": {
                                "type": "object",
                                "properties": {
                                    "fact": {
                                        "type": "string",
                                        "description": "Fato concreto e verificável do tópico",
                                    },
                                    "analogy": {
                                        "type": "string",
                                        "description": "Analogia visual original e inesperada que explica o fato",
                                    },
                                },
                                "required": ["fact", "analogy"],
                            },
                        },
                        "payoff": {
                            "type": "string",
                            "description": "Conclusão que fecha o loop do hook com uma reflexão surpreendente",
                        },
                        "cta": {
                            "type": "string",
                            "description": (
                                "Call to action opcional, 1 frase máxima. "
                                "NÃO use 'não esqueça de se inscrever' nem variações. "
                                "Use string vazia se não for natural ao tópico."
                            ),
                        },
                    },
                    "required": ["hook", "beats", "payoff", "cta"],
                },
            }
        ],
        tool_choice={"type": "tool", "name": "submit_script"},
        messages=[{"role": "user", "content": user}],
    )


def _parse_script(response: anthropic.types.Message) -> Script:
    for block in response.content:
        if block.type == "tool_use" and block.name == "submit_script":
            inp = block.input
            beats = [
                ScriptBeat(fact=b["fact"], analogy=b["analogy"])
                for b in inp["beats"]
            ]
            cta = inp.get("cta") or None  # "" → None
            return Script(
                hook=inp["hook"],
                beats=beats,
                payoff=inp["payoff"],
                cta=cta,
            )
    raise ValueError("Claude não retornou tool_use com 'submit_script'")


# ── Agente principal ───────────────────────────────────────────────────────────


@traceable(name=AGENT_NAME)
def write_script(topic_id: UUID) -> Script:
    """Gera e persiste roteiro para um tópico.

    Args:
        topic_id: UUID do tópico em topics.

    Returns:
        Script com hook, beats, payoff e cta.

    Raises:
        ValueError: Se o script gerado for muito similar a um existente (> 0.80)
                    ou se não houver vídeo draft para o tópico.
    """
    t0 = time.monotonic()
    client = anthropic.Anthropic()
    conn = _get_conn()
    video_id: str | None = None
    response: anthropic.types.Message | None = None

    try:
        # 1. Busca tópico + canal + video_id do rascunho
        topic = _fetch_topic_and_video(conn, topic_id)
        video_id = str(topic["video_id"])
        log.info("Gerando roteiro para: '%s'", topic["title"])

        # 2. Busca claims do vídeo (ordenados do melhor para o pior)
        claims = _fetch_claims(conn, video_id)
        log.info("  %d claims carregados", len(claims))

        # 3. Gera roteiro via Claude
        log.info("Chamando %s...", CLAUDE_MODEL)
        response = _call_claude(client, topic, claims)
        script = _parse_script(response)
        log.info(
            "Claude retornou script  (%d in / %d out tokens)",
            response.usage.input_tokens,
            response.usage.output_tokens,
        )
        log.info("  hook: %s", script.hook)

        # 4. Embedding do full_text (gerado pelo model_validator do Script)
        embedder = _get_embedder()
        embedding: np.ndarray = embedder.encode(script.full_text)

        # 5. Verifica similaridade com scripts existentes do canal
        max_sim = _max_similarity(conn, topic["channel_id"], embedding)
        if max_sim is not None:
            log.info("  similarity máxima com scripts existentes: %.3f", max_sim)
        if max_sim is not None and max_sim > SIMILARITY_THRESHOLD:
            raise ValueError(
                f"Script muito similar a roteiro existente "
                f"(sim={max_sim:.3f} > {SIMILARITY_THRESHOLD}). "
                "Abortando para evitar conteúdo repetido."
            )

        # 6. Persiste script na tabela scripts
        script_id = _insert_script(conn, video_id, script, embedding, max_sim)
        log.info("Script persistido: %s", script_id)

        # 7. Atualiza status do vídeo para scripted
        _update_video_status(conn, video_id)
        log.info("Vídeo %s → status=scripted", video_id)
        conn.commit()

        # 8. Registra execução em agent_runs
        duration_ms = int((time.monotonic() - t0) * 1000)
        cost_usd = (
            response.usage.input_tokens * INPUT_COST_PER_TOK
            + response.usage.output_tokens * OUTPUT_COST_PER_TOK
        )
        _record_agent_run(conn, topic_id, video_id, response, script, duration_ms, "success")
        conn.commit()

        log.info(
            "write_script concluído: %dms  (custo $%.4f)",
            duration_ms,
            cost_usd,
        )
        return script

    except Exception as exc:
        conn.rollback()
        duration_ms = int((time.monotonic() - t0) * 1000)
        log.error("write_script falhou: %s", exc)
        try:
            _record_agent_run(
                conn, topic_id, video_id, response, None, duration_ms, "failed", str(exc)
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

    # Busca o primeiro vídeo com status 'draft'
    _conn = psycopg2.connect(_db_url, connect_timeout=10)
    with _conn.cursor() as _cur:
        _cur.execute(
            """
            SELECT v.id, v.topic_id, t.title
            FROM   videos v
            JOIN   topics t ON t.id = v.topic_id
            WHERE  v.status = 'draft'
            ORDER  BY v.created_at ASC
            LIMIT  1
            """
        )
        _row = _cur.fetchone()
    _conn.close()

    if not _row:
        print("Nenhum vídeo com status='draft' encontrado.")
        print("Execute primeiro: uv run python agents/researcher.py")
        sys.exit(1)

    _video_id, _topic_id, _title = _row
    print(f"Vídeo:  [{str(_video_id)[:8]}] {_title}")
    print("Iniciando write_script...\n")

    _script = write_script(UUID(str(_topic_id)))

    print(f"\n{'─' * 60}")
    print("Roteiro gerado:")
    print(f"  hook:   {_script.hook}")
    print(f"  beats:  {len(_script.beats)} blocos")
    for i, b in enumerate(_script.beats, 1):
        print(f"    [{i}] fato:     {b.fact[:70]}...")
        print(f"         analogia: {b.analogy[:70]}...")
    print(f"  payoff: {_script.payoff[:80]}...")
    if _script.cta:
        print(f"  cta:    {_script.cta}")
    print(f"\nfull_text ({len(_script.full_text)} chars):")
    print(_script.full_text[:600] + ("..." if len(_script.full_text) > 600 else ""))
