---
trigger: always_on
---

## Arquitetura Apogee

### Estrutura de pastas
```
Apogee/
  agents/        ← um arquivo por agente (topic_miner.py, researcher.py, etc.)
  workers/       ← workers RQ
  models.py      ← VideoSpec e todos os Pydantic models (fonte da verdade)
  db.py          ← funções de acesso ao banco (sem ORM)
  embeddings.py  ← funções de embedding e similarity
migrations/      ← arquivos SQL numerados (001_initial.sql, 002_add_x.sql)
scripts/         ← utilitários (smoke_test.py, seed_channel.py, check_env.py)
remotion/        ← projeto Node separado, não misture com Python
```

### Regras de agentes
- Cada agente é uma função Python pura: recebe input tipado, retorna output tipado
- Agentes não acessam o banco diretamente — recebem e retornam Pydantic models
- Quem persiste é o orquestrador (`pipeline.py`), não o agente
- Toda execução registra entrada e saída em `agent_runs`

### Regras de dados
- O contrato entre agentes é sempre `VideoSpec` de `models.py`
- Nunca passe dicionários crus entre agentes — use os models Pydantic
- Similaridade de embeddings usa cosine similarity via pgvector ou scikit-learn

### Custo operacional
- Sempre estime o custo antes de implementar um novo call LLM
- Budget mensal alvo: < $10/mês para Claude API no volume inicial