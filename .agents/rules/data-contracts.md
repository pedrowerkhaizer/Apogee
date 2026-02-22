---
trigger: always_on
---

## Contratos de dados

### Thresholds de negócio (não altere sem decisão explícita)
- Similaridade de tópicos: rejeita se cosine_similarity > 0.75
- Similaridade de scripts: bloqueia se cosine_similarity > 0.80
- template_score: pausa pipeline se score > 0.70
- Fact checker: rejeita script se risk_score > 0.60, máximo 2 tentativas

### Status válidos
- topics.status: pending | approved | rejected | published
- videos.status: draft | scripted | rendered | published | failed
- agent_runs.status: success | failed | retry

### Campos obrigatórios no VideoSpec
- hook: máximo 200 caracteres
- beats: exatamente 3 itens (ScriptBeat com fact + analogy)
- payoff: obrigatório
- cta: opcional, sem "não esqueça de se inscrever"

### Embeddings
- Modelo: all-MiniLM-L6-v2
- Dimensão: 384
- Sempre normalize antes de calcular cosine similarity