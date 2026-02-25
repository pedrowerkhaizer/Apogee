"""scripts/alerting.py — Alertas e rotação de logs para o pipeline Apogee.

Funções:
    send_alert(title, message, level)  — Slack webhook ou log de fallback
    rotate_logs(max_days)              — Remove logs mais antigos que N dias
    daily_summary(conn)                — Resumo diário de execução (vídeos, custo, erros)

Configuração via .env:
    SLACK_WEBHOOK_URL  — URL do webhook Slack (opcional)
    ALERT_EMAIL        — Email para notificações (não implementado, preparado para futuro)

Uso:
    from scripts.alerting import send_alert, rotate_logs, daily_summary
"""

from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import psycopg2
import psycopg2.extras
import requests
from dotenv import load_dotenv

load_dotenv()

log = logging.getLogger(__name__)

ROOT = Path(__file__).parent.parent
LOGS_DIR = ROOT / "artifacts" / "logs"

SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL", "")


# ── Alertas ────────────────────────────────────────────────────────────────────


def send_alert(title: str, message: str, level: str = "error") -> None:
    """Envia alerta para Slack (se configurado) ou loga como fallback.

    Args:
        title:   Título curto do alerta (ex: "Vídeo falhou").
        message: Detalhes do alerta.
        level:   "error" | "warning" | "info"
    """
    emoji = {"error": ":red_circle:", "warning": ":warning:", "info": ":white_check_mark:"}.get(
        level, ":bell:"
    )
    log_fn = {"error": log.error, "warning": log.warning, "info": log.info}.get(level, log.info)

    full_message = f"[{level.upper()}] {title}: {message}"
    log_fn(full_message)

    if not SLACK_WEBHOOK_URL:
        return

    payload = {
        "text": f"{emoji} *Apogee Engine* — {title}",
        "attachments": [
            {
                "color": {"error": "danger", "warning": "warning", "info": "good"}.get(level, ""),
                "text": message,
                "footer": f"Apogee Pipeline • {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
            }
        ],
    }
    try:
        resp = requests.post(SLACK_WEBHOOK_URL, json=payload, timeout=5)
        if resp.status_code != 200:
            log.warning("Slack webhook retornou %d: %s", resp.status_code, resp.text)
    except Exception as exc:
        log.warning("Falha ao enviar alerta Slack: %s", exc)


# ── Rotação de logs ────────────────────────────────────────────────────────────


def rotate_logs(max_days: int = 30) -> int:
    """Remove arquivos de log mais antigos que max_days dias.

    Args:
        max_days: Número de dias para manter (default: 30).

    Returns:
        Número de arquivos removidos.
    """
    if not LOGS_DIR.exists():
        return 0

    cutoff = datetime.now(timezone.utc) - timedelta(days=max_days)
    removed = 0

    for log_file in LOGS_DIR.glob("*.log"):
        mtime = datetime.fromtimestamp(log_file.stat().st_mtime, tz=timezone.utc)
        if mtime < cutoff:
            try:
                log_file.unlink()
                log.info("Log removido (rotação): %s", log_file.name)
                removed += 1
            except OSError as exc:
                log.warning("Erro ao remover log %s: %s", log_file.name, exc)

    if removed:
        log.info("Rotação de logs: %d arquivo(s) removido(s) (> %d dias)", removed, max_days)
    return removed


# ── Sumário diário ─────────────────────────────────────────────────────────────


def daily_summary(conn: psycopg2.extensions.connection) -> dict:
    """Gera e envia sumário diário de execução do pipeline.

    Args:
        conn: Conexão psycopg2 ao Supabase.

    Returns:
        Dict com métricas: videos_rendered, videos_failed, total_cost_usd, errors.
    """
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        # Vídeos do último dia
        cur.execute(
            """
            SELECT
                COUNT(*) FILTER (WHERE status = 'rendered')  AS rendered,
                COUNT(*) FILTER (WHERE status = 'published') AS published,
                COUNT(*) FILTER (WHERE status = 'failed')    AS failed
            FROM videos
            WHERE updated_at >= NOW() - INTERVAL '24 hours'
            """
        )
        videos = dict(cur.fetchone())  # type: ignore[arg-type]

        # Custo do último dia
        cur.execute(
            """
            SELECT COALESCE(SUM(cost_usd), 0) AS total_cost
            FROM agent_runs
            WHERE created_at >= NOW() - INTERVAL '24 hours'
            """
        )
        cost_row = cur.fetchone()
        total_cost = float(cost_row["total_cost"]) if cost_row else 0.0  # type: ignore[index]

        # Erros do último dia
        cur.execute(
            """
            SELECT agent_name, error_message
            FROM agent_runs
            WHERE status = 'failed'
              AND created_at >= NOW() - INTERVAL '24 hours'
            ORDER BY created_at DESC
            LIMIT 5
            """
        )
        errors = [dict(r) for r in cur.fetchall()]

    summary = {
        "videos_rendered": int(videos.get("rendered", 0)),
        "videos_published": int(videos.get("published", 0)),
        "videos_failed": int(videos.get("failed", 0)),
        "total_cost_usd": round(total_cost, 4),
        "recent_errors": errors,
    }

    level = "error" if summary["videos_failed"] > 0 else "info"
    lines = [
        f"Vídeos renderizados: {summary['videos_rendered']}",
        f"Vídeos publicados:   {summary['videos_published']}",
        f"Vídeos com falha:    {summary['videos_failed']}",
        f"Custo total (24h):   US$ {summary['total_cost_usd']:.4f}",
    ]
    if errors:
        lines.append(f"Últimos erros: {', '.join(e['agent_name'] for e in errors)}")

    send_alert("Sumário diário", "\n".join(lines), level=level)
    return summary


if __name__ == "__main__":
    import argparse

    _parser = argparse.ArgumentParser(description="Alerting — rotação de logs e sumário")
    _parser.add_argument("--rotate", action="store_true", help="Rotacionar logs agora")
    _parser.add_argument("--summary", action="store_true", help="Gerar sumário diário")
    _parser.add_argument("--max-days", type=int, default=30, help="Dias para manter logs (default: 30)")
    _args = _parser.parse_args()

    if _args.rotate:
        n = rotate_logs(_args.max_days)
        print(f"Rotação: {n} log(s) removido(s)")

    if _args.summary:
        _db_url = os.getenv("SUPABASE_DB_URL")
        if not _db_url:
            print("SUPABASE_DB_URL não definido")
            sys.exit(1)
        _conn = psycopg2.connect(_db_url, connect_timeout=10)
        try:
            s = daily_summary(_conn)
            print(json.dumps(s, indent=2, ensure_ascii=False))
        finally:
            _conn.close()
