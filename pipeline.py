"""pipeline.py — Orquestrador do pipeline Apogee.

Encadeia: TopicMiner → aprovação manual → Researcher → Scriptwriter → FactChecker.
Usa RQ para enfileirar cada etapa e APScheduler para execução diária.

Uso manual:
    uv run python pipeline.py          # inicia schedule (cron via PIPELINE_SCHEDULE)
    uv run python pipeline.py --once   # executa uma vez imediatamente
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import time
from datetime import datetime, timezone
from uuid import UUID

import psycopg2
import psycopg2.extras
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from dotenv import load_dotenv
from redis import Redis
from rq import Queue
from rq.job import Job, JobStatus

from models import Claim, FactCheckResult, Script, ScriptBeat, VideoSpec, VideoStatus

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# ── Constantes / env ───────────────────────────────────────────────────────────

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
PIPELINE_SCHEDULE = os.getenv("PIPELINE_SCHEDULE", "0 8 * * *")
APPROVAL_TIMEOUT_HOURS = int(os.getenv("APPROVAL_TIMEOUT_HOURS", "48"))
APPROVAL_POLL_INTERVAL_S = int(os.getenv("APPROVAL_POLL_INTERVAL_S", "60"))

MAX_FACT_CHECK_ATTEMPTS = 2  # máximo de tentativas scriptwriter+factchecker por vídeo

# ── Conexões ───────────────────────────────────────────────────────────────────


def _get_conn() -> psycopg2.extensions.connection:
    db_url = os.getenv("SUPABASE_DB_URL")
    if not db_url:
        raise RuntimeError("SUPABASE_DB_URL não definido no .env")
    return psycopg2.connect(db_url, connect_timeout=10)


def _get_redis() -> Redis:
    return Redis.from_url(REDIS_URL)


# ── Helpers de banco ───────────────────────────────────────────────────────────


def _fetch_channel_id(conn: psycopg2.extensions.connection) -> UUID:
    """Retorna o UUID do primeiro canal em channel_config."""
    with conn.cursor() as cur:
        cur.execute("SELECT id FROM channel_config ORDER BY created_at ASC LIMIT 1")
        row = cur.fetchone()
    if not row:
        raise RuntimeError("Nenhum canal encontrado em channel_config. Execute seed_channel.py.")
    return UUID(str(row[0]))


def _fetch_approved_topic_ids(
    conn: psycopg2.extensions.connection,
    channel_id: UUID,
    candidate_ids: list[UUID],
) -> list[UUID]:
    """Retorna IDs dos tópicos candidatos com status='approved'."""
    if not candidate_ids:
        return []
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id FROM topics
            WHERE  channel_id = %s
              AND  status = 'approved'
              AND  id = ANY(%s)
            """,
            (str(channel_id), [str(tid) for tid in candidate_ids]),
        )
        return [UUID(str(row[0])) for row in cur.fetchall()]


def _fetch_video_id(
    conn: psycopg2.extensions.connection, topic_id: UUID
) -> UUID | None:
    """Retorna o UUID do vídeo draft vinculado ao tópico, ou None se não existir."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id FROM videos WHERE topic_id = %s ORDER BY created_at DESC LIMIT 1",
            (str(topic_id),),
        )
        row = cur.fetchone()
    return UUID(str(row[0])) if row else None


def _mark_video_failed(
    conn: psycopg2.extensions.connection, video_id: UUID, reason: str
) -> None:
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE videos SET status = 'failed', error_message = %s, updated_at = NOW() WHERE id = %s",
            (reason, str(video_id)),
        )
    conn.commit()


def _record_orchestrator_run(
    conn: psycopg2.extensions.connection,
    channel_id: UUID,
    status: str,
    topics_processed: int,
    videos_approved: int,
    videos_failed: int,
    duration_ms: int,
    error_message: str | None = None,
) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO agent_runs
                (agent_name, video_id, topic_id, status,
                 input_json, output_json,
                 tokens_input, tokens_output, cost_usd, duration_ms, error_message)
            VALUES ('orchestrator', NULL, NULL, %s, %s, %s, 0, 0, 0.0, %s, %s)
            """,
            (
                status,
                psycopg2.extras.Json(
                    {"channel_id": str(channel_id), "topics_processed": topics_processed}
                ),
                psycopg2.extras.Json(
                    {"videos_approved": videos_approved, "videos_failed": videos_failed}
                ),
                duration_ms,
                error_message,
            ),
        )
    conn.commit()


def _build_video_spec(
    conn: psycopg2.extensions.connection, video_id: UUID
) -> VideoSpec:
    """Reconstrói VideoSpec a partir do banco de dados."""
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """
            SELECT v.id, v.channel_id, v.topic_id, t.title,
                   v.status, v.created_at,
                   s.hook, s.beats, s.payoff, s.cta,
                   s.template_score, s.similarity_score
            FROM   videos v
            JOIN   topics  t ON t.id = v.topic_id
            JOIN   scripts s ON s.video_id = v.id
            WHERE  v.id = %s
            ORDER  BY s.created_at DESC
            LIMIT  1
            """,
            (str(video_id),),
        )
        row = dict(cur.fetchone())

        cur.execute(
            "SELECT claim_text, source_url, risk_score, verified FROM claims WHERE video_id = %s",
            (str(video_id),),
        )
        claim_rows = cur.fetchall()

    beats_raw = row["beats"] if isinstance(row["beats"], list) else json.loads(row["beats"])
    beats = [ScriptBeat(fact=b["fact"], analogy=b["analogy"]) for b in beats_raw]

    script = Script(
        hook=row["hook"],
        beats=beats,
        payoff=row["payoff"],
        cta=row["cta"] or None,
    )

    claims = [
        Claim(
            claim_text=r["claim_text"],
            source_url=r["source_url"],
            confidence=round(1.0 - float(r["risk_score"]), 6),
            verified=bool(r["verified"]),
        )
        for r in claim_rows
    ]

    return VideoSpec(
        video_id=UUID(str(row["id"])),
        topic_id=UUID(str(row["topic_id"])),
        topic_title=row["title"],
        channel_id=UUID(str(row["channel_id"])),
        status=VideoStatus(row["status"]),
        claims=claims,
        script=script,
        similarity_score=float(row["similarity_score"]) if row["similarity_score"] is not None else None,
        template_score=float(row["template_score"]) if row["template_score"] is not None else None,
        created_at=row["created_at"],
    )


# ── RQ helpers ─────────────────────────────────────────────────────────────────


def _wait_job(job: Job, name: str, poll_s: float = 1.0) -> object:
    """Aguarda conclusão do job RQ e retorna o resultado, ou lança RuntimeError."""
    terminal = {JobStatus.FINISHED, JobStatus.FAILED, JobStatus.STOPPED, JobStatus.CANCELED}
    while job.get_status() not in terminal:
        time.sleep(poll_s)

    final_status = job.get_status()
    if final_status != JobStatus.FINISHED:
        try:
            exc_info = job.latest_result().exc_string
        except Exception:
            exc_info = str(final_status)
        raise RuntimeError(f"Job '{name}' terminou com status={final_status}: {exc_info}")

    return job.latest_result().return_value


# ── Gate de aprovação ──────────────────────────────────────────────────────────


def _wait_for_approvals(
    conn: psycopg2.extensions.connection,
    channel_id: UUID,
    candidate_ids: list[UUID],
) -> list[UUID]:
    """Aguarda aprovação manual de tópicos. Retorna IDs aprovados dentro do timeout."""
    if not candidate_ids:
        return []

    deadline = time.time() + APPROVAL_TIMEOUT_HOURS * 3600
    log.info(
        "Aguardando aprovação manual de %d tópico(s)... (timeout=%dh, poll=%ds)",
        len(candidate_ids),
        APPROVAL_TIMEOUT_HOURS,
        APPROVAL_POLL_INTERVAL_S,
    )

    while time.time() < deadline:
        approved = _fetch_approved_topic_ids(conn, channel_id, candidate_ids)
        if approved:
            log.info("  %d tópico(s) aprovado(s): %s", len(approved), approved)
            return approved
        remaining_h = (deadline - time.time()) / 3600
        log.info("  Nenhum tópico aprovado ainda. Próxima verificação em %ds (%.1fh restantes).",
                 APPROVAL_POLL_INTERVAL_S, remaining_h)
        time.sleep(APPROVAL_POLL_INTERVAL_S)

    log.warning("Timeout de aprovação atingido (%dh). Encerrando pipeline.", APPROVAL_TIMEOUT_HOURS)
    return []


# ── Processamento de tópico ────────────────────────────────────────────────────


def _process_topic(
    redis_conn: Redis,
    conn: psycopg2.extensions.connection,
    topic_id: UUID,
) -> VideoSpec | None:
    """Executa Researcher → Scriptwriter → FactChecker para um tópico.

    Returns:
        VideoSpec completo se aprovado, None se falhou após max tentativas.
    """
    log.info("[%s] Iniciando Researcher...", str(topic_id)[:8])
    q_researcher = Queue("researcher", connection=redis_conn)
    job = q_researcher.enqueue(
        "workers.researcher_worker.run", topic_id, job_timeout=120
    )
    _wait_job(job, "research_topic")

    video_id = _fetch_video_id(conn, topic_id)
    if video_id is None:
        log.error("[%s] Vídeo não encontrado após researcher.", str(topic_id)[:8])
        return None

    log.info("[%s] video_id=%s — iniciando Scriptwriter...", str(topic_id)[:8], str(video_id)[:8])

    q_scriptwriter = Queue("scriptwriter", connection=redis_conn)
    q_fact_checker = Queue("fact_checker", connection=redis_conn)

    for attempt in range(1, MAX_FACT_CHECK_ATTEMPTS + 1):
        log.info("[%s] Tentativa %d/%d — write_script...", str(video_id)[:8], attempt, MAX_FACT_CHECK_ATTEMPTS)
        job_script = q_scriptwriter.enqueue(
            "workers.scriptwriter_worker.run", topic_id, job_timeout=180
        )
        _wait_job(job_script, "write_script")

        log.info("[%s] Tentativa %d/%d — check_script...", str(video_id)[:8], attempt, MAX_FACT_CHECK_ATTEMPTS)
        job_fact = q_fact_checker.enqueue(
            "workers.fact_checker_worker.run", video_id, job_timeout=60
        )
        result_dict = _wait_job(job_fact, "check_script")
        fact_result = FactCheckResult(**result_dict)

        if fact_result.approved:
            log.info("[%s] FactChecker aprovado (risk_score=%.3f).", str(video_id)[:8], fact_result.risk_score)
            break

        log.warning(
            "[%s] FactChecker rejeitou (risk_score=%.3f). Issues: %s",
            str(video_id)[:8],
            fact_result.risk_score,
            fact_result.issues,
        )
        if attempt == MAX_FACT_CHECK_ATTEMPTS:
            reason = f"fact_checker: max {MAX_FACT_CHECK_ATTEMPTS} tentativas esgotadas"
            _mark_video_failed(conn, video_id, reason)
            log.error("[%s] Vídeo marcado como 'failed'.", str(video_id)[:8])
            return None

    spec = _build_video_spec(conn, video_id)
    log.info("[%s] VideoSpec construído com sucesso.", str(video_id)[:8])
    return spec


# ── Orquestrador principal ─────────────────────────────────────────────────────


def run_pipeline(channel_id: UUID) -> list[VideoSpec]:
    """Executa o pipeline completo para o canal.

    Args:
        channel_id: UUID do canal em channel_config.

    Returns:
        Lista de VideoSpec aprovados nesta execução.
    """
    t0 = time.monotonic()
    log.info("=" * 60)
    log.info("Pipeline iniciado — canal %s", str(channel_id)[:8])
    log.info("=" * 60)

    redis_conn = _get_redis()
    conn = _get_conn()
    results: list[VideoSpec] = []
    videos_failed = 0

    try:
        # 1. Mine Topics
        log.info("Etapa 1/4 — TopicMiner")
        q_miner = Queue("topic_miner", connection=redis_conn)
        job_miner = q_miner.enqueue(
            "workers.topic_miner_worker.run", channel_id, job_timeout=300
        )
        topics_created: list[dict] = _wait_job(job_miner, "mine_topics")
        topic_ids = [UUID(t["id"]) for t in topics_created]
        log.info("  %d tópico(s) criados com status='pending'.", len(topic_ids))

        # 2. Gate de aprovação
        log.info("Etapa 2/4 — Aprovação manual")
        approved_ids = _wait_for_approvals(conn, channel_id, topic_ids)
        if not approved_ids:
            log.warning("Nenhum tópico aprovado. Pipeline encerrado.")
            _record_orchestrator_run(
                conn, channel_id, "success", len(topic_ids), 0, 0,
                int((time.monotonic() - t0) * 1000),
            )
            return []

        # 3. Processa cada tópico aprovado
        log.info("Etapa 3/4 — Processando %d tópico(s) aprovado(s).", len(approved_ids))
        for topic_id in approved_ids:
            try:
                spec = _process_topic(redis_conn, conn, topic_id)
                if spec:
                    results.append(spec)
                else:
                    videos_failed += 1
            except Exception as exc:
                log.error("[%s] Erro ao processar tópico: %s", str(topic_id)[:8], exc)
                videos_failed += 1

        # 4. Registra run do orquestrador
        duration_ms = int((time.monotonic() - t0) * 1000)
        log.info(
            "Etapa 4/4 — Pipeline concluído em %dms | aprovados=%d | falhos=%d",
            duration_ms,
            len(results),
            videos_failed,
        )
        _record_orchestrator_run(
            conn, channel_id, "success",
            len(approved_ids), len(results), videos_failed, duration_ms,
        )
        return results

    except Exception as exc:
        duration_ms = int((time.monotonic() - t0) * 1000)
        log.error("Pipeline falhou: %s", exc)
        try:
            _record_orchestrator_run(
                conn, channel_id, "failed", 0, 0, 0, duration_ms, str(exc)
            )
        except Exception:
            pass
        raise

    finally:
        conn.close()


# ── Execução principal ─────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Apogee Pipeline Orchestrator")
    parser.add_argument(
        "--once",
        action="store_true",
        help="Executa o pipeline uma vez imediatamente e encerra.",
    )
    args = parser.parse_args()

    _conn = _get_conn()
    try:
        _channel_id = _fetch_channel_id(_conn)
    finally:
        _conn.close()

    log.info("Canal: %s", _channel_id)

    if args.once:
        log.info("Modo --once: executando pipeline agora.")
        _specs = run_pipeline(_channel_id)
        log.info("Pipeline concluído: %d vídeo(s) aprovado(s).", len(_specs))
    else:
        log.info("Iniciando scheduler (PIPELINE_SCHEDULE='%s').", PIPELINE_SCHEDULE)
        scheduler = BlockingScheduler(timezone="America/Sao_Paulo")
        scheduler.add_job(
            run_pipeline,
            CronTrigger.from_crontab(PIPELINE_SCHEDULE, timezone="America/Sao_Paulo"),
            args=[_channel_id],
            id="apogee_pipeline",
            name="Apogee Daily Pipeline",
            misfire_grace_time=3600,
        )
        log.info("Scheduler ativo — cron: '%s'. Pressione Ctrl+C para encerrar.", PIPELINE_SCHEDULE)
        try:
            scheduler.start()
        except (KeyboardInterrupt, SystemExit):
            log.info("Scheduler encerrado.")
