"""scripts/check_env.py – Apogee environment health checker.

Testa cada integração e imprime OK ou FAIL por serviço.
Não importa nada de apogee/ para manter zero dependências circulares.

Uso:
    cp .env.example .env    # preencha com valores reais
    docker compose up -d    # inicia Redis local
    uv run python scripts/check_env.py
"""

from __future__ import annotations

import asyncio
import importlib
import logging
import os
import sys
import time
from typing import Callable

from dotenv import load_dotenv

load_dotenv()

# ── Logging mínimo ──────────────────────────────────────────────────────────
logging.basicConfig(level=logging.WARNING)

# ── Cores ANSI ──────────────────────────────────────────────────────────────
GREEN = "\033[92m"
RED = "\033[91m"
RESET = "\033[0m"
BOLD = "\033[1m"


def _ok(label: str, detail: str = "") -> None:
    suffix = f"  → {detail}" if detail else ""
    print(f"  {GREEN}[OK]  {RESET} {label}{suffix}")


def _fail(label: str, reason: str = "") -> None:
    suffix = f"  → {reason}" if reason else ""
    print(f"  {RED}[FAIL]{RESET} {label}{suffix}")


# ── Checks individuais ───────────────────────────────────────────────────────

def check_env_vars() -> bool:
    """Verifica se todas as variáveis obrigatórias estão definidas."""
    required = [
        "SUPABASE_URL",
        "SUPABASE_KEY",
        "SUPABASE_DB_URL",
        "ANTHROPIC_API_KEY",
        "REDIS_URL",
        "LANGSMITH_API_KEY",
    ]
    missing = [v for v in required if not os.getenv(v)]
    if missing:
        _fail("ENV VARS", f"ausentes: {', '.join(missing)}")
        return False
    _ok("ENV VARS")
    return True


def check_redis() -> bool:
    """Testa conexão com Redis via ping."""
    try:
        import redis  # noqa: PLC0415

        url = os.getenv("REDIS_URL", "redis://localhost:6379")
        client = redis.from_url(url, socket_connect_timeout=3)
        response = client.ping()
        if response:
            _ok("Redis", url)
            return True
        _fail("Redis", "ping retornou False")
        return False
    except Exception as exc:
        _fail("Redis", str(exc))
        return False


def check_supabase_rest() -> bool:
    """Testa a API REST do Supabase (não requer tabelas existentes)."""
    try:
        from supabase import create_client  # noqa: PLC0415

        url = os.getenv("SUPABASE_URL", "")
        key = os.getenv("SUPABASE_KEY", "")
        if not url or not key:
            _fail("Supabase REST", "SUPABASE_URL ou SUPABASE_KEY não definidos")
            return False

        client = create_client(url, key)
        # Tenta buscar da tabela agent_runs; PGRST116 = tabela não existe ainda (OK)
        response = client.table("agent_runs").select("id").limit(1).execute()
        _ok("Supabase REST", f"{url}")
        return True
    except Exception as exc:
        msg = str(exc)
        # PGRST116 = relação não existe — esperado antes das migrations
        if "PGRST116" in msg or "does not exist" in msg:
            _ok("Supabase REST", "conectado (tabela agent_runs ainda não existe – OK)")
            return True
        _fail("Supabase REST", msg[:120])
        return False


def check_postgres_direct() -> bool:
    """Testa conexão direta ao Postgres via psycopg2."""
    try:
        import psycopg2  # noqa: PLC0415

        db_url = os.getenv("SUPABASE_DB_URL", "")
        if not db_url:
            _fail("Postgres direct", "SUPABASE_DB_URL não definido")
            return False

        conn = psycopg2.connect(db_url, connect_timeout=5)
        cur = conn.cursor()
        cur.execute("SELECT 1")
        cur.close()
        conn.close()
        _ok("Postgres direct", "SELECT 1 OK")
        return True
    except Exception as exc:
        _fail("Postgres direct", str(exc)[:120])
        return False


def check_anthropic() -> bool:
    """Verifica que a chave Anthropic é aceita (lista modelos, sem consumo de tokens)."""
    try:
        import anthropic  # noqa: PLC0415

        key = os.getenv("ANTHROPIC_API_KEY", "")
        if not key:
            _fail("Anthropic", "ANTHROPIC_API_KEY não definido")
            return False

        client = anthropic.Anthropic(api_key=key)
        models = client.models.list()
        count = len(list(models))
        _ok("Anthropic", f"{count} modelos disponíveis")
        return True
    except Exception as exc:
        _fail("Anthropic", str(exc)[:120])
        return False


def check_langsmith() -> bool:
    """Verifica que o LangSmith aceita a chave (lista projetos)."""
    try:
        import langsmith  # noqa: PLC0415

        key = os.getenv("LANGSMITH_API_KEY", "")
        if not key:
            _fail("LangSmith", "LANGSMITH_API_KEY não definido")
            return False

        client = langsmith.Client(api_key=key)
        projects = list(client.list_projects())
        _ok("LangSmith", f"{len(projects)} projeto(s)")
        return True
    except Exception as exc:
        _fail("LangSmith", str(exc)[:120])
        return False


def check_sentence_transformers() -> bool:
    """Carrega o modelo all-MiniLM-L6-v2 e verifica dimensão do embedding (384)."""
    try:
        from sentence_transformers import SentenceTransformer  # noqa: PLC0415

        model = SentenceTransformer("all-MiniLM-L6-v2")
        embedding = model.encode("test")
        dim = len(embedding)
        if dim != 384:
            _fail("sentence-transformers", f"dimensão inesperada: {dim} (esperado 384)")
            return False
        _ok("sentence-transformers", f"dim={dim}")
        return True
    except Exception as exc:
        _fail("sentence-transformers", str(exc)[:120])
        return False


def check_edge_tts() -> bool:
    """Lista vozes do Edge-TTS para confirmar que o pacote funciona."""
    try:
        import edge_tts  # noqa: PLC0415

        voices = asyncio.run(edge_tts.list_voices())
        pt_voices = [v for v in voices if v["Locale"].startswith("pt-BR")]
        _ok("Edge-TTS", f"{len(pt_voices)} vozes pt-BR disponíveis")
        return True
    except Exception as exc:
        _fail("Edge-TTS", str(exc)[:120])
        return False


# ── Runner ───────────────────────────────────────────────────────────────────

CHECKS: list[tuple[str, Callable[[], bool]]] = [
    ("ENV VARS", check_env_vars),
    ("Redis", check_redis),
    ("Supabase REST", check_supabase_rest),
    ("Postgres direct", check_postgres_direct),
    ("Anthropic", check_anthropic),
    ("LangSmith", check_langsmith),
    ("sentence-transformers", check_sentence_transformers),
    ("Edge-TTS", check_edge_tts),
]


def main() -> None:
    """Executa todos os checks e imprime um sumário final."""
    print(f"\n{BOLD}Apogee – Environment Check{RESET}\n")

    results: dict[str, bool] = {}
    start = time.monotonic()

    for name, fn in CHECKS:
        try:
            results[name] = fn()
        except Exception as exc:
            _fail(name, f"erro inesperado: {exc}")
            results[name] = False

    elapsed = time.monotonic() - start
    passed = sum(results.values())
    total = len(results)

    print(f"\n{'─' * 40}")
    print(f"  {passed}/{total} serviços OK  ({elapsed:.1f}s)\n")

    if passed < total:
        sys.exit(1)


if __name__ == "__main__":
    main()
