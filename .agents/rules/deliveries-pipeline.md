---
trigger: manual
---

# FASE 1 — PIPELINE DE CONTEÚDO

## E1.1 — Topic Miner

Crie `apogee/agents/topic_miner.py`:

- Função principal: `mine_topics(channel_config: ChannelConfig) -> list[Topic]`
- Chama Claude API com prompt que gera 20 candidatos de tópico de curiosidade científica verificável em pt-BR, cada um com gancho de plot twist ou dado contraintuitivo
- Para cada tópico gerado:
  - Calcula embedding com sentence-transformers all-MiniLM-L6-v2
  - Consulta tabela topics (últimos 50 aprovados) e calcula cosine similarity via pgvector
  - Rejeita automaticamente se similarity > 0.75
  - Persiste aprovados com status pending e similarity_score
- Registra execução em agent_runs com tokens, custo e duração
- Instrumentado com @traceable do LangSmith
- Bloco if __name__ == "__main__" com exemplo de execução manual

---

## E1.2 — Researcher

Crie `apogee/agents/researcher.py`:

- Função principal: `research_topic(topic: Topic) -> list[Claim]`
- Chama Claude API com prompt de pesquisa estruturada (sem web search — conhecimento interno do modelo)
- Retorna 3–5 claims no formato Claim(claim_text, source_url, confidence)
- Prompt instrui o modelo a ser conservador na auto-avaliação de confidence
- Persiste claims na tabela claims
- Registra em agent_runs
- Instrumentado com @traceable

---

## E1.3 — Scriptwriter

Crie `apogee/agents/scriptwriter.py`:

- Função principal: `write_script(topic: Topic, claims: list[Claim]) -> Script`
- Chama Claude API com prompt que gera roteiro no formato Script
- Estrutura obrigatória de saída:
  - hook: 1–2 frases, máximo 8 palavras, pergunta ou afirmação contraintuitiva
  - beats: exatamente 3 itens, cada um com 1 fato + 1 analogia original
  - payoff: conclusão que fecha o loop do hook
  - cta: máximo 1 frase, sem "não esqueça de se inscrever"
- Após geração: calcula embedding do full_text e compara com scripts existentes no banco
- Bloqueia se cosine_similarity > 0.80
- Registra em agent_runs
- Instrumentado com @traceable

---

## E1.4 — Fact Checker

Crie `apogee/agents/fact_checker.py`:

- Função principal: `check_script(script: Script, claims: list[Claim]) -> FactCheckResult`
- FactCheckResult: { risk_score: float, issues: list[str], approved: bool }
- Audita:
  - Claims sem fonte associada no script
  - Linguagem de certeza absoluta em claims com confidence < 0.7 (ex: "é provado que", "sempre", "nunca") — substitui por linguagem calibrada
- Retorna risk_score (0.0–1.0) e lista de problemas
- Se risk_score > 0.60: rejeita o script (approved=False)
- Máximo de 2 tentativas por script (controle no orquestrador)
- Registra em agent_runs
- Instrumentado com @traceable

---

## E1.5 — Orquestrador

Crie `apogee/pipeline.py`:

- Função principal: `run_pipeline(channel_id: UUID) -> list[VideoSpec]`
- Encadeia: TopicMiner → aprovação manual via UPDATE no banco → Researcher → Scriptwriter → FactChecker
- Usa RQ para enfileirar cada etapa como job separado
- Workers ficam em `apogee/workers/`
- Cria um worker por agente: topic_miner_worker.py, researcher_worker.py, scriptwriter_worker.py, fact_checker_worker.py
- Se FactChecker rejeitar: reenvia para Scriptwriter (máximo 2 tentativas, depois marca video como failed)
- Persiste VideoSpec completo no banco ao final

---

## E1.6 — LangSmith

- Todos os agentes já devem estar instrumentados com @traceable (feito nas entregas anteriores)
- Crie `scripts/verify_langsmith.py` que:
  - Executa uma chamada de teste ao Claude
  - Confirma que o trace aparece no LangSmith
  - Imprime o link do trace ou FAIL com erro

Meta de validação da Fase 1: 10 VideoSpecs completos no banco com scripts aprovados pelo Fact Checker e todos os agent_runs auditados.

---

# FASE 2 — RENDER MVP

## E2.1 — TTS

Crie `apogee/agents/tts.py`:

- Função principal: `generate_audio(script: Script) -> dict[str, float]`
- Recebe script segmentado por beat
- Gera arquivo .mp3 por segmento via edge-tts (voz pt-BR-AntonioNeural)
- Extrai duração real de cada segmento com mutagen
- Retorna {beat_id: duration_sec}
- Salva arquivos em output/audio/{video_id}/

---

## E2.2 — Storyboard Director

Crie `apogee/agents/storyboard_director.py`:

- Função principal: `build_storyboard(script: Script, durations: dict[str, float]) -> Storyboard`
- Regra-based, sem LLM
- Monta storyboard com timestamps precisos baseados nas durações reais do TTS:
```python
Storyboard:
  scenes: list[Scene]

Scene:
  id: str
  t0: float
  t1: float
  type: str  # hook_text | diagram | chart | text_animation | payoff_text | cta_text
  text: Optional[str]
  asset_id: Optional[str]
```

---

## E2.3 — Remotion MVP

Crie o projeto Remotion em `remotion/`:

- Composição `ShortExplainer` que recebe storyboard completo via inputProps
- Suporte a cenas: hook_text, text_animation, payoff_text, cta_text
- Animação de entrada: fade + slide
- Background com gradiente configurável via props
- Legendas sincronizadas com áudio
- Ratio 9:16, 1080x1920, 30fps

---

## E2.4 — Python → Remotion

Crie `apogee/render.py`:

- Função principal: `render_video(video_id: UUID, storyboard: Storyboard) -> RenderResult`
- Escreve input_props.json em disco
- Chama: `npx remotion render ShortExplainer output/renders/{video_id}.mp4 --props=input_props.json`
- Captura stdout/stderr para auditoria
- Persiste resultado na tabela renders

---

## E2.5 — FFmpeg

Crie `apogee/postprocess.py`:

- Função principal: `postprocess(video_path: str) -> str`
- Aplica:
  - Normalização de loudness: LUFS -14 (padrão YouTube)
  - Compressão: CRF 23, H.264
  - Extração de thumbnail: frame do segundo 3
- Retorna caminho do arquivo final processado

---

# FASE 3 — ANTI-TEMPLATE

## E3.1 — template_score

Adicione em `apogee/pipeline.py` cálculo de template_score antes de cada render:
```python
template_score = (
  0.4 * scene_reuse_rate +       # % de cenas iguais nos últimos 10 vídeos
  0.4 * script_similarity_max +  # maior similarity de script nos últimos 50
  0.2 * asset_reuse_rate         # % de assets reutilizados
)
```

Se template_score > 0.70: pausa o pipeline e notifica o operador via log com nível WARNING antes de renderizar.

---

## E3.2 — Biblioteca de variação

No projeto Remotion, implemente:

- 5 estilos de hook: texto puro, pergunta com countdown, afirmação + pausa, dado numérico destacado, visual first
- 3 estruturas de beat: linear, comparativo, cronológico
- 2 paletas de cor alternadas por vídeo baseadas em hash do topic_id (não sequencialmente)

O Storyboard Director escolhe variações para minimizar scene_reuse_rate.

---

## E3.3 — Asset Generator

Crie `apogee/agents/asset_generator.py`:

- Função principal: `generate_asset(claim: Claim) -> Asset`
- Para claims com dados numéricos: gráfico de barras ou linha com matplotlib
- Para claims comparativos: diagrama lado a lado
- Exporta como PNG em output/assets/{video_id}/
- Resolução adequada para 9:16
- Calcula checksum SHA256 do arquivo para detectar reuso

---

# FASE 4 — ANALYTICS

## E4.1 — Import de métricas

Crie `scripts/import_metrics.py`:

- Lê CSV exportado do YouTube Studio
- Valida colunas esperadas: video_id, date, views, avg_view_duration_sec, ctr, likes, shares
- Faz upsert em performance_daily (respeita UNIQUE video_id + date)
- Imprime resumo: N linhas importadas, N atualizadas, N erros

---

## E4.2 — Queries Metabase

Crie `analytics/queries.sql` com as seguintes queries prontas para uso no Metabase:

1. Retenção média por hook_style
2. CTR por tom de título
3. template_score vs performance (correlação)
4. Custo por vídeo (tokens Claude + TTS + infra)
5. Vídeos em risco de repetição (similarity > 0.65)

---

## E4.3 — Ranker de tópicos

Crie `apogee/ranker.py`:

- Função `train_ranker(df: pd.DataFrame) -> Pipeline` que treina modelo scikit-learn
- Features: similarity_score, hook_style_encoded, has_numeric_claim, topic_category_encoded, day_of_week
- Target: avg_view_duration_sec
- Modelo: GradientBoostingRegressor
- Salva modelo treinado em models/ranker.pkl com joblib
- Função `score_topics(topics: list[Topic]) -> list[tuple[Topic, float]]` que aplica o ranker e retorna tópicos ordenados por score previsto
- O Topic Miner deve chamar score_topics antes de persistir candidatos

---

Implemente entrega por entrega. Após cada entrega, liste os arquivos criados e o critério de conclusão. Aguarde minha confirmação antes de avançar.