"""scripts/verify_langsmith.py — Verificação LangSmith para o pipeline Apogee.

Duas verificações:
  1. Trace real: executa chamada Claude API via @traceable e confirma que o
     trace chegou ao LangSmith, imprimindo o link direto.
  2. Auditoria de agentes: verifica que @traceable existe nos 4 agentes.

Uso:
    uv run python scripts/verify_langsmith.py
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import os

import anthropic
from dotenv import load_dotenv
from langsmith import Client as LangSmithClient
from langsmith.run_helpers import trace

load_dotenv()

# ── Constantes ─────────────────────────────────────────────────────────────────

LANGCHAIN_PROJECT = os.getenv("LANGCHAIN_PROJECT", "apogee-dev")

AGENTS: dict[str, str] = {
    "topic_miner":  "agents/topic_miner.py",
    "researcher":   "agents/researcher.py",
    "scriptwriter": "agents/scriptwriter.py",
    "fact_checker": "agents/fact_checker.py",
}

# Modelo mais barato para verificação (não gera custo significativo)
_VERIFY_MODEL = "claude-haiku-4-5-20251001"

# ── Verificação 1 — Trace real ─────────────────────────────────────────────────


def verify_trace() -> bool:
    """Executa probe com Claude API e confirma trace no LangSmith.

    Usa o context manager `trace` com client explícito para garantir que o
    flush da fila de envio seja aguardado antes de tentar ler o trace de volta.

    Returns:
        True se OK, False se FAIL.
    """
    print("[1/2] Trace real via Claude API...")

    langsmith_key = os.getenv("LANGSMITH_API_KEY")
    if not langsmith_key:
        print("  FAIL: LANGSMITH_API_KEY não definido no .env")
        return False

    anthropic_key = os.getenv("ANTHROPIC_API_KEY")
    if not anthropic_key:
        print("  FAIL: ANTHROPIC_API_KEY não definido no .env")
        return False

    tracing_enabled = os.getenv("LANGCHAIN_TRACING_V2", "").lower()
    if tracing_enabled != "true":
        print("  FAIL: LANGCHAIN_TRACING_V2 não está definido como 'true'")
        return False

    # Usa client explícito para poder acessar tracing_queue após o trace
    ls_client = LangSmithClient()
    client_ai = anthropic.Anthropic()

    run_id: str | None = None
    try:
        with trace(
            "langsmith_verify",
            run_type="chain",
            inputs={"prompt": "Responda apenas a palavra: ok"},
            project_name=LANGCHAIN_PROJECT,
            client=ls_client,
        ) as run_tree:
            resp = client_ai.messages.create(
                model=_VERIFY_MODEL,
                max_tokens=10,
                messages=[{"role": "user", "content": "Responda apenas a palavra: ok"}],
            )
            answer = resp.content[0].text.strip()
            run_tree.outputs = {"answer": answer}
            run_id = str(run_tree.id)
    except Exception as exc:
        print(f"  FAIL: chamada Claude API ou trace falhou — {exc}")
        return False

    if not run_id:
        print("  FAIL: run_id não capturado — trace pode estar desabilitado")
        return False

    # Aguarda flush completo da fila de envio para o servidor LangSmith
    if ls_client.tracing_queue is not None:
        ls_client.tracing_queue.join()
    else:
        time.sleep(3)

    # Retry com backoff: LangSmith pode ter um delay de indexação após receber o run
    run = None
    last_exc: Exception | None = None
    for attempt in range(1, 7):          # até ~15s total (1+2+2+2+2+2+3)
        wait_s = 1 if attempt == 1 else 2
        time.sleep(wait_s)
        try:
            run = ls_client.read_run(run_id)
            break
        except Exception as exc:
            last_exc = exc

    if run is None:
        print(f"  FAIL: trace não encontrado no LangSmith após retries (run_id={run_id}) — {last_exc}")
        return False

    try:
        url = ls_client.get_run_url(run=run, project_name=LANGCHAIN_PROJECT)
        print(f"  TRACE OK  {url}")
    except Exception as exc:
        # Fallback: imprime o run_id e o projeto quando URL completa não está disponível
        print(f"  TRACE OK  (run_id={run_id}; get_run_url falhou: {exc})")

    return True


# ── Verificação 2 — Auditoria de agentes ──────────────────────────────────────


def verify_agents() -> bool:
    """Verifica que @traceable está presente em todos os agentes.

    Returns:
        True se todos OK, False se algum MISSING.
    """
    print("[2/2] Auditoria @traceable nos agentes...")

    root = Path(__file__).parent.parent
    all_ok = True

    for name, rel_path in AGENTS.items():
        agent_path = root / rel_path
        if not agent_path.exists():
            status = "MISSING"
            detail = "(arquivo não encontrado)"
            all_ok = False
        else:
            text = agent_path.read_text(encoding="utf-8")
            if "@traceable" in text:
                status = "OK     "
                detail = ""
            else:
                status = "MISSING"
                detail = "(sem @traceable)"
                all_ok = False

        print(f"  [{status}] {name:<20s} {rel_path}  {detail}".rstrip())

    return all_ok


# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    sep = "═" * 52
    print(sep)
    print("Apogee — Verificação LangSmith")
    print(sep)
    print()

    ok_trace  = verify_trace()
    print()
    ok_agents = verify_agents()
    print()

    checks_ok = sum([ok_trace, ok_agents])
    print(sep)
    if checks_ok == 2:
        print(f"RESULTADO: 2/2 verificações OK")
    else:
        print(f"RESULTADO: {checks_ok}/2 verificações OK  ← veja FAILs acima")
    print(sep)

    sys.exit(0 if checks_ok == 2 else 1)


if __name__ == "__main__":
    main()
