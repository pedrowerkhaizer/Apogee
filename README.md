# Apogee Engine

Automated YouTube video pipeline — topic mining → scripting → rendering → publishing.

## Setup

```bash
cp .env.example .env        # preencha com credenciais reais
docker compose up -d        # inicia Redis local
uv sync --all-extras        # instala dependências Python
uv run python scripts/check_env.py   # valida conexões
```

## Stack

| Camada | Tecnologia |
|--------|-----------|
| LLM | Claude (Anthropic) + LangSmith |
| Database | Supabase (Postgres + pgvector) |
| Queue | RQ + Redis |
| Embeddings | sentence-transformers (`all-MiniLM-L6-v2`) |
| TTS | Edge-TTS (`pt-BR-AntonioNeural`) |
| Render | Remotion via subprocess |
| Post-proc | FFmpeg |
