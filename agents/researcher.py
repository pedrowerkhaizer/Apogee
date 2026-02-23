"""agents/researcher.py — Researcher agent.

Para um dado tópico, gera 3–5 claims factuais verificáveis usando
conhecimento interno do Claude (sem web search) e os persiste no banco.
Se ainda não houver vídeo para o tópico, cria um rascunho com status='draft'.

Uso manual:
    uv run python agents/researcher.py
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

import anthropic
import psycopg2
import psycopg2.extras
from dotenv import load_dotenv
from langsmith import traceable

from models import Claim

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# ── Constantes ─────────────────────────────────────────────────────────────────

AGENT_NAME = "researcher"
CLAUDE_MODEL = "claude-sonnet-4-6"
MIN_CLAIMS = 3
MAX_CLAIMS = 5

INPUT_COST_PER_TOK = 3.0 / 1_000_000
OUTPUT_COST_PER_TOK = 15.0 / 1_000_000

# ── Helpers de banco ───────────────────────────────────────────────────────────


def _get_conn() -> psycopg2.extensions.connection:
    db_url = os.getenv("SUPABASE_DB_URL")
    if not db_url:
        raise RuntimeError("SUPABASE_DB_URL não definido no .env")
    return psycopg2.connect(db_url, connect_timeout=10)


def _fetch_topic(conn: psycopg2.extensions.connection, topic_id: UUID) -> dict:
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """
            SELECT t.id, t.title, t.rationale, t.channel_id,
                   c.niche, c.tone, c.target_audience
            FROM   topics t
            JOIN   channel_config c ON c.id = t.channel_id
            WHERE  t.id = %s
            """,
            (str(topic_id),),
        )
        row = cur.fetchone()
    if not row:
        raise ValueError(f"Tópico não encontrado: {topic_id}")
    return dict(row)


def _get_or_create_video(conn: psycopg2.extensions.connection, topic: dict) -> str:
    """Retorna o video_id existente ou cria um rascunho draft."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id FROM videos WHERE topic_id = %s LIMIT 1",
            (str(topic["id"]),),
        )
        row = cur.fetchone()
        if row:
            log.info("Vídeo existente encontrado: %s", row[0])
            return str(row[0])

        cur.execute(
            """
            INSERT INTO videos (channel_id, topic_id, title, status)
            VALUES (%s, %s, %s, 'draft')
            RETURNING id
            """,
            (str(topic["channel_id"]), str(topic["id"]), topic["title"]),
        )
        video_id = str(cur.fetchone()[0])
        log.info("Vídeo draft criado: %s", video_id)
        return video_id


def _persist_claims(
    conn: psycopg2.extensions.connection, video_id: str, claims: list[Claim]
) -> None:
    with conn.cursor() as cur:
        for claim in claims:
            cur.execute(
                """
                INSERT INTO claims
                    (video_id, claim_text, source_url, verified, risk_score)
                VALUES (%s, %s, %s, false, %s)
                """,
                (
                    video_id,
                    claim.claim_text,
                    claim.source_url,
                    round(1.0 - claim.confidence, 6),
                ),
            )


def _record_agent_run(
    conn: psycopg2.extensions.connection,
    topic_id: UUID,
    video_id: str | None,
    response: anthropic.types.Message | None,
    claims: list[Claim],
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
                    {
                        "claims_count": len(claims),
                        "claims": [c.model_dump() for c in claims],
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
    client: anthropic.Anthropic, topic: dict
) -> anthropic.types.Message:
    system = (
        "Você é um pesquisador factual rigoroso especializado em ciência e tecnologia.\n"
        "Seu trabalho é identificar claims factuais verificáveis sobre um tópico.\n\n"
        "Diretrizes obrigatórias:\n"
        "- Use apenas conhecimento consolidado — sem especulação\n"
        "- confidence > 0.8 APENAS se tiver certeza absoluta do fato\n"
        "- confidence entre 0.5–0.8 para fatos prováveis mas com nuances\n"
        "- NUNCA invente URLs — source_url deve ser uma URL real e conhecida, ou string vazia\n"
        "- Fontes aceitas: nature.com, pubmed.ncbi.nlm.nih.gov, arxiv.org, science.org, "
        "sciencedirect.com, ibge.gov.br, gov.br\n"
        "- Todos os claim_text em português do Brasil (pt-BR)"
    )
    user = (
        f"Tópico: {topic['title']}\n"
        f"Contexto: {topic.get('rationale', '')}\n"
        f"Nicho do canal: {topic.get('niche', '')}\n\n"
        f"Pesquise e retorne entre {MIN_CLAIMS} e {MAX_CLAIMS} claims factuais "
        "verificáveis e surpreendentes sobre este tópico. "
        "Cada claim deve ser uma afirmação factual específica com dados concretos "
        "que sustentaria o argumento do vídeo."
    )

    return client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=1024,
        system=system,
        tools=[
            {
                "name": "submit_claims",
                "description": "Submete os claims factuais verificáveis sobre o tópico",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "claims": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "claim_text": {
                                        "type": "string",
                                        "description": "Afirmação factual verificável e específica em pt-BR",
                                    },
                                    "source_url": {
                                        "type": "string",
                                        "description": (
                                            "URL da fonte real (ex: https://pubmed.ncbi.nlm.nih.gov/...). "
                                            "Deixe vazio se não souber com certeza — nunca invente."
                                        ),
                                    },
                                    "confidence": {
                                        "type": "number",
                                        "minimum": 0.0,
                                        "maximum": 1.0,
                                        "description": (
                                            "Confiança na veracidade (0.0–1.0). "
                                            "Seja conservador: >0.8 apenas se absolutamente certo."
                                        ),
                                    },
                                },
                                "required": ["claim_text", "source_url", "confidence"],
                            },
                            "minItems": MIN_CLAIMS,
                            "maxItems": MAX_CLAIMS,
                        }
                    },
                    "required": ["claims"],
                },
            }
        ],
        tool_choice={"type": "tool", "name": "submit_claims"},
        messages=[{"role": "user", "content": user}],
    )


def _parse_claims(response: anthropic.types.Message) -> list[Claim]:
    for block in response.content:
        if block.type == "tool_use" and block.name == "submit_claims":
            return [
                Claim(
                    claim_text=c["claim_text"],
                    source_url=c["source_url"] or None,  # "" → None
                    confidence=float(c["confidence"]),
                )
                for c in block.input["claims"]
            ]
    raise ValueError("Claude não retornou tool_use com 'submit_claims'")


# ── Agente principal ───────────────────────────────────────────────────────────


@traceable(name=AGENT_NAME)
def research_topic(topic_id: UUID) -> list[Claim]:
    """Pesquisa e persiste claims factuais para um tópico.

    Args:
        topic_id: UUID do tópico em topics.

    Returns:
        Lista de Claim com os fatos verificáveis encontrados.
    """
    t0 = time.monotonic()
    client = anthropic.Anthropic()
    conn = _get_conn()
    video_id: str | None = None

    try:
        # 1. Busca tópico + contexto do canal
        topic = _fetch_topic(conn, topic_id)
        log.info("Pesquisando: '%s'", topic["title"])

        # 2. Gera claims via Claude
        log.info("Chamando %s...", CLAUDE_MODEL)
        response = _call_claude(client, topic)
        claims = _parse_claims(response)
        log.info(
            "Claude retornou %d claims  (%d in / %d out tokens)",
            len(claims),
            response.usage.input_tokens,
            response.usage.output_tokens,
        )
        for c in claims:
            url_tag = f" [{c.source_url}]" if c.source_url else ""
            log.info("  [%.2f]%s %s", c.confidence, url_tag, c.claim_text[:80])

        # 3. Garante que há um vídeo draft vinculado ao tópico
        video_id = _get_or_create_video(conn, topic)

        # 4. Persiste claims
        _persist_claims(conn, video_id, claims)
        conn.commit()

        # 5. Registra execução
        duration_ms = int((time.monotonic() - t0) * 1000)
        cost_usd = (
            response.usage.input_tokens * INPUT_COST_PER_TOK
            + response.usage.output_tokens * OUTPUT_COST_PER_TOK
        )
        _record_agent_run(conn, topic_id, video_id, response, claims, duration_ms, "success")
        conn.commit()

        log.info(
            "research_topic concluído: %d claims em %dms  (custo $%.4f)",
            len(claims),
            duration_ms,
            cost_usd,
        )
        return claims

    except Exception as exc:
        conn.rollback()
        duration_ms = int((time.monotonic() - t0) * 1000)
        log.error("research_topic falhou: %s", exc)
        try:
            _record_agent_run(
                conn, topic_id, video_id, None, [], duration_ms, "failed", str(exc)
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

    # Busca o primeiro tópico com status 'pending'
    _conn = psycopg2.connect(_db_url, connect_timeout=10)
    with _conn.cursor() as _cur:
        _cur.execute(
            "SELECT id, title FROM topics WHERE status = 'pending' ORDER BY created_at ASC LIMIT 1"
        )
        _row = _cur.fetchone()
    _conn.close()

    if not _row:
        print("Nenhum tópico com status='pending' encontrado.")
        print("Execute primeiro: uv run python agents/topic_miner.py")
        sys.exit(1)

    _topic_id, _topic_title = _row
    print(f"Tópico: [{str(_topic_id)[:8]}] {_topic_title}")
    print("Iniciando research_topic...\n")

    _claims = research_topic(UUID(str(_topic_id)))

    print(f"\n{'─' * 60}")
    print(f"{len(_claims)} claims persistidos:")
    for _c in _claims:
        url_str = f"  → {_c.source_url}" if _c.source_url else "  → sem URL"
        print(f"  [conf={_c.confidence:.2f}] {_c.claim_text}")
        print(url_str)
