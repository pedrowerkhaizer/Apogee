"""agents/fact_checker.py — Fact Checker agent.

Audita claims associadas a um vídeo, detecta ausência de fonte e linguagem de
certeza absoluta em claims de baixa confiança, corrige no banco e calcula um
risk_score. Sem chamadas LLM — checagem puramente rule-based.

Uso manual:
    uv run python agents/fact_checker.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# Garante que a raiz do projeto está em sys.path ao rodar como script
# (deve vir ANTES dos imports third-party pois `from models import ...` é module-level)
sys.path.insert(0, str(Path(__file__).parent.parent))

import logging
import os
import re
import time
from uuid import UUID

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv
from langsmith import traceable

from models import FactCheckResult

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# ── Constantes ─────────────────────────────────────────────────────────────────

AGENT_NAME = "fact_checker"
RISK_PER_NO_SOURCE = 0.2
RISK_PER_ABSOLUTE_LANGUAGE = 0.15
APPROVAL_THRESHOLD = 0.60  # risk_score > 0.60 → rejected

# Padrões de linguagem absoluta → substituição calibrada
# Ordem importa: padrões mais longos primeiro para evitar sobreposição
ABSOLUTE_LANGUAGE: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\bé provado que\b", re.IGNORECASE), "evidências sugerem que"),
    (re.compile(r"\bcertamente\b", re.IGNORECASE), "evidências sugerem"),
    (re.compile(r"\bimpossível\b", re.IGNORECASE), "raramente"),
    (re.compile(r"\bsempre\b", re.IGNORECASE), "na maioria dos casos"),
    (re.compile(r"\bnunca\b", re.IGNORECASE), "raramente"),
]

# Threshold de confiança: aplica auditoria de linguagem apenas abaixo deste valor
# risk_score > 0.30 equivale a confidence < 0.70
LOW_CONFIDENCE_THRESHOLD = 0.30  # risk_score na tabela claims

# ── Helpers de banco ───────────────────────────────────────────────────────────


def _get_conn() -> psycopg2.extensions.connection:
    db_url = os.getenv("SUPABASE_DB_URL")
    if not db_url:
        raise RuntimeError("SUPABASE_DB_URL não definido no .env")
    return psycopg2.connect(db_url, connect_timeout=10)


def _fetch_script_hook(
    conn: psycopg2.extensions.connection, video_id: UUID
) -> str | None:
    """Retorna o hook do script vinculado ao vídeo, ou None se não existir."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT hook FROM scripts WHERE video_id = %s LIMIT 1",
            (str(video_id),),
        )
        row = cur.fetchone()
    return row[0] if row else None


def _fetch_claims(
    conn: psycopg2.extensions.connection, video_id: UUID
) -> list[dict]:
    """Retorna todas as claims do vídeo ordenadas por risk_score ASC."""
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """
            SELECT id, claim_text, source_url, risk_score
            FROM   claims
            WHERE  video_id = %s
            ORDER  BY risk_score ASC
            """,
            (str(video_id),),
        )
        return [dict(r) for r in cur.fetchall()]


def _update_claim_text(
    conn: psycopg2.extensions.connection, claim_id: str, new_text: str
) -> None:
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE claims SET claim_text = %s WHERE id = %s",
            (new_text, claim_id),
        )


def _update_video_status(
    conn: psycopg2.extensions.connection, video_id: UUID, status: str
) -> None:
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE videos SET status = %s, updated_at = NOW() WHERE id = %s",
            (status, str(video_id)),
        )


def _record_agent_run(
    conn: psycopg2.extensions.connection,
    video_id: UUID,
    result: FactCheckResult | None,
    claims_audited: int,
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
                    {"video_id": str(video_id), "claims_audited": claims_audited}
                ),
                psycopg2.extras.Json(
                    result.model_dump() if result else None
                ),
                duration_ms,
                error_message,
            ),
        )


# ── Lógica de auditoria ────────────────────────────────────────────────────────


def _apply_language_substitutions(text: str) -> tuple[str, list[str]]:
    """Aplica substituições de linguagem absoluta.

    Returns:
        (new_text, detected_patterns) — detected_patterns é lista com os
        padrões encontrados, vazia se nenhuma substituição ocorreu.
    """
    detected: list[str] = []
    new_text = text
    for pattern, replacement in ABSOLUTE_LANGUAGE:
        substituted = pattern.sub(replacement, new_text)
        if substituted != new_text:
            detected.append(pattern.pattern)
            new_text = substituted
    return new_text, detected


# ── Agente principal ───────────────────────────────────────────────────────────


@traceable(name=AGENT_NAME)
def check_script(video_id: UUID) -> FactCheckResult:
    """Audita claims de um vídeo e calcula risk_score.

    Args:
        video_id: UUID do vídeo em videos.

    Returns:
        FactCheckResult com risk_score, issues e approved.
    """
    t0 = time.monotonic()
    conn = _get_conn()
    result: FactCheckResult | None = None

    try:
        # 1. Carrega contexto do script e claims
        hook = _fetch_script_hook(conn, video_id)
        if hook:
            log.info("Auditando vídeo: '%s'", hook[:72])
        else:
            log.info("Auditando vídeo: %s (sem script encontrado)", video_id)

        claims = _fetch_claims(conn, video_id)
        log.info("  %d claims carregadas", len(claims))

        if not claims:
            raise ValueError(f"Nenhuma claim encontrada para o vídeo: {video_id}")

        issues: list[str] = []
        n_no_source = 0
        n_absolute_language = 0

        # 2. Auditoria de cada claim
        for claim in claims:
            claim_id = str(claim["id"])
            claim_text: str = claim["claim_text"]
            source_url = claim.get("source_url")
            claim_risk: float = float(claim["risk_score"])

            # 2a. Claim sem fonte
            if not source_url:
                n_no_source += 1
                excerpt = claim_text[:60] + ("..." if len(claim_text) > 60 else "")
                issues.append(f"Claim sem fonte: '{excerpt}'")
                log.info("  [sem fonte] %s", excerpt)

            # 2b. Linguagem absoluta (apenas para claims de baixa confiança)
            if claim_risk > LOW_CONFIDENCE_THRESHOLD:
                new_text, detected = _apply_language_substitutions(claim_text)
                if detected:
                    n_absolute_language += 1
                    excerpt = claim_text[:60] + ("..." if len(claim_text) > 60 else "")
                    issues.append(
                        f"Linguagem absoluta corrigida em claim: '{excerpt}'"
                    )
                    log.info(
                        "  [linguagem absoluta] %d padrão(ões) corrigido(s): %s",
                        len(detected),
                        excerpt,
                    )
                    _update_claim_text(conn, claim_id, new_text)

        # 3. Calcula risk_score final
        raw_score = n_no_source * RISK_PER_NO_SOURCE + n_absolute_language * RISK_PER_ABSOLUTE_LANGUAGE
        risk_score = round(min(1.0, raw_score), 6)
        approved = risk_score <= APPROVAL_THRESHOLD

        log.info(
            "  risk_score=%.3f  (sem_fonte=%d, linguagem_absoluta=%d)  approved=%s",
            risk_score,
            n_no_source,
            n_absolute_language,
            approved,
        )

        # 4. Atualiza status do vídeo
        new_status = "scripted" if approved else "draft"
        _update_video_status(conn, video_id, new_status)
        log.info("  Vídeo %s → status=%s", video_id, new_status)

        conn.commit()

        # 5. Monta resultado e registra execução
        result = FactCheckResult(
            risk_score=risk_score,
            issues=issues,
            approved=approved,
        )

        duration_ms = int((time.monotonic() - t0) * 1000)
        _record_agent_run(conn, video_id, result, len(claims), duration_ms, "success")
        conn.commit()

        log.info("check_script concluído: %dms", duration_ms)
        return result

    except Exception as exc:
        conn.rollback()
        duration_ms = int((time.monotonic() - t0) * 1000)
        log.error("check_script falhou: %s", exc)
        try:
            _record_agent_run(conn, video_id, None, 0, duration_ms, "failed", str(exc))
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

    # Busca o primeiro vídeo com status 'scripted' que tenha script associado
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
    print("Iniciando check_script...\n")

    _result = check_script(UUID(str(_video_id)))

    print(f"\n{'─' * 60}")
    print(f"Resultado:")
    print(f"  risk_score: {_result.risk_score:.3f}")
    print(f"  approved:   {_result.approved}")
    if _result.issues:
        print(f"  issues ({len(_result.issues)}):")
        for _issue in _result.issues:
            print(f"    • {_issue}")
    else:
        print("  issues:     nenhum")
