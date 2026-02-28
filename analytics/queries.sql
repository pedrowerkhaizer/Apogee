-- =============================================================================
-- Apogee Engine — Queries para Metabase
-- Conectado ao Supabase (PostgreSQL + pgvector)
--
-- Como usar no Metabase:
--   1. Adicione o Supabase como fonte de dados (PostgreSQL connection string)
--   2. Crie uma "Native Query" para cada bloco abaixo
--   3. Salve cada query como uma "Question" e agrupe em um Dashboard
--
-- Atualizado em: 2026-02-28
-- =============================================================================


-- =============================================================================
-- QUERY 1: Retenção média por hook_style
-- =============================================================================
--
-- Objetivo:
--   Identificar qual estilo de hook gera maior retenção média de audiência.
--   O hook_style não existe como coluna no banco — é determinado em runtime
--   pelo Remotion usando hash(topic_id) % 5. Aqui derivamos o mesmo valor
--   via abs(hashtext(v.topic_id::text)) % 5, que é deterministicamente
--   consistente com a lógica de apresentação.
--
-- Os 5 estilos de hook disponíveis:
--   0 = curiosidade   → desperta curiosidade sobre algo pouco conhecido
--   1 = dado_chocante → abre com estatística ou fato surpreendente
--   2 = pergunta      → começa com uma pergunta direta ao espectador
--   3 = narrativa     → inicia com mini-história ou situação
--   4 = comparacao    → compara dois cenários opostos
--
-- Como interpretar:
--   Ordene pela coluna avg_retention_sec (decrescente).
--   Hook styles no topo retêm espectadores por mais tempo em média.
--   Use video_count para avaliar a significância estatística — estilos com
--   poucos vídeos (<5) devem ser interpretados com cautela.
--   Recomendação: priorizando hook styles com avg_retention_sec > 60s e
--   video_count >= 5 para decisões de produção.
-- =============================================================================

SELECT
    CASE (abs(hashtext(v.topic_id::text)) % 5)
        WHEN 0 THEN 'curiosidade'
        WHEN 1 THEN 'dado_chocante'
        WHEN 2 THEN 'pergunta'
        WHEN 3 THEN 'narrativa'
        WHEN 4 THEN 'comparacao'
    END                              AS hook_style,
    ROUND(AVG(pd.avg_view_duration_sec)::NUMERIC, 1) AS avg_retention_sec,
    COUNT(DISTINCT v.id)             AS video_count
FROM scripts s
JOIN videos v        ON v.id  = s.video_id
JOIN performance_daily pd ON pd.video_id = v.id
WHERE pd.avg_view_duration_sec IS NOT NULL
GROUP BY hook_style
ORDER BY avg_retention_sec DESC NULLS LAST;


-- =============================================================================
-- QUERY 2: CTR médio por tom de título
-- =============================================================================
--
-- Objetivo:
--   Descobrir quais "tons de abertura" de hook geram maior taxa de clique (CTR)
--   nos thumbnails/títulos do YouTube.
--   O "tom" é aproximado pelas primeiras 2 palavras do campo hook, que
--   representam a promessa inicial ao espectador.
--
-- Exemplos de tons identificados:
--   "Por que"  → tom interrogativo
--   "Como o"   → tom explicativo
--   "O segredo"→ tom de revelação
--   "Você sabia" → tom de curiosidade direta
--
-- Como interpretar:
--   CTR acima de 4% é considerado bom no YouTube.
--   CTR acima de 8% é excelente.
--   Combinações de palavras no topo da lista devem ser priorizadas na criação
--   de novos hooks. Filtre por video_count >= 3 para evitar ruído estatístico.
--   Limitado a 20 resultados para visualização clara em gráfico de barras.
-- =============================================================================

SELECT
    split_part(s.hook, ' ', 1) || ' ' || split_part(s.hook, ' ', 2) AS title_tone,
    ROUND(AVG(pd.ctr)::NUMERIC, 4)   AS avg_ctr,
    COUNT(DISTINCT v.id)             AS video_count
FROM scripts s
JOIN videos v        ON v.id  = s.video_id
JOIN performance_daily pd ON pd.video_id = v.id
WHERE pd.ctr IS NOT NULL
  AND s.hook IS NOT NULL
  AND s.hook <> ''
GROUP BY title_tone
HAVING COUNT(DISTINCT v.id) >= 1
ORDER BY avg_ctr DESC NULLS LAST
LIMIT 20;


-- =============================================================================
-- QUERY 3: Correlação template_score vs avg_view_duration_sec
-- =============================================================================
--
-- Objetivo:
--   Verificar se templates muito reutilizados (template_score alto) impactam
--   negativamente o tempo médio de visualização.
--   template_score varia de 0 a 1: valores próximos de 1 indicam que o
--   template visual e estrutura do script são muito similares a vídeos
--   anteriores, potencialmente causando fadiga de conteúdo na audiência.
--
-- Threshold de pausa do pipeline: template_score > 0.70
--   Vídeos com score acima disso são bloqueados automaticamente pelo pipeline.
--   Esta query avalia o impacto real na retenção antes e após esse threshold.
--
-- Como interpretar:
--   Se avg_view_duration_sec cai conforme template_score_bucket aumenta,
--   o threshold de pausa (0.70) está calibrado corretamente.
--   Se não há correlação clara, o threshold pode precisar de ajuste.
--   Visualize como gráfico de linha no Metabase com template_score_bucket
--   no eixo X e avg_view_duration_sec no eixo Y.
-- =============================================================================

SELECT
    ROUND(s.template_score::NUMERIC, 1) AS template_score_bucket,
    ROUND(AVG(pd.avg_view_duration_sec)::NUMERIC, 1) AS avg_view_duration_sec,
    COUNT(DISTINCT v.id)                AS video_count
FROM scripts s
JOIN videos v        ON v.id  = s.video_id
JOIN performance_daily pd ON pd.video_id = v.id
WHERE pd.avg_view_duration_sec IS NOT NULL
  AND s.template_score IS NOT NULL
GROUP BY template_score_bucket
ORDER BY template_score_bucket ASC;


-- =============================================================================
-- QUERY 4: Custo operacional por vídeo
-- =============================================================================
--
-- Objetivo:
--   Mapear o custo total de Claude API (e outros agentes com custo) por vídeo,
--   somando todos os agent_runs associados ao video_id.
--   Auxilia no controle do budget mensal (meta: < $10/mês total).
--
-- Agentes com custo registrado:
--   - topic_miner: ~$0.002 por run
--   - researcher: ~$0.005 por run
--   - scriptwriter: ~$0.016 por run
--   - fact_checker, tts, storyboard_director: cost_usd = 0.0
--
-- Como interpretar:
--   Vídeos no topo da lista são os mais caros de produzir (múltiplas retentativas
--   de fact_checker/scriptwriter inflam o custo).
--   agent_runs_count alto com custo baixo indica muitos runs de agentes sem LLM.
--   agent_runs_count alto com custo alto indica retentativas de agentes LLM.
--   Monitore o total acumulado — se SUM(total_cost_usd) > $10 no mês, revisar
--   o número de retentativas permitidas no pipeline.
-- =============================================================================

SELECT
    v.id                                          AS video_id,
    v.title,
    v.status                                      AS video_status,
    ROUND(SUM(ar.cost_usd)::NUMERIC, 6)           AS total_cost_usd,
    COUNT(ar.id)                                  AS agent_runs_count,
    v.created_at::DATE                            AS video_date
FROM agent_runs ar
JOIN videos v ON v.id = ar.video_id
WHERE ar.video_id IS NOT NULL
GROUP BY v.id, v.title, v.status, v.created_at
ORDER BY total_cost_usd DESC;


-- =============================================================================
-- QUERY 5: Vídeos em risco de repetição de conteúdo
-- =============================================================================
--
-- Objetivo:
--   Identificar scripts com similarity_score alto em relação a conteúdo
--   anterior do canal, indicando risco de repetição de tema ou argumento.
--   Permite revisão manual antes da publicação.
--
-- Thresholds do sistema:
--   similarity_score > 0.65 → alerta (esta query)
--   similarity_score > 0.80 → bloqueio automático pelo pipeline
--
-- O similarity_score é calculado via cosine similarity entre o embedding
--   do script atual e os últimos 50 scripts do canal (VECTOR(384),
--   modelo all-MiniLM-L6-v2). Valor 1.0 = cópia exata.
--
-- Como interpretar:
--   Scripts com score entre 0.65 e 0.80 não foram bloqueados automaticamente
--   mas apresentam sobreposição temática relevante. Revise o hook e os beats
--   para garantir que o ângulo abordado é suficientemente diferente.
--   Scripts com score > 0.80 aqui indicam falha no gate do pipeline —
--   investigar agent_runs para o video_id correspondente.
-- =============================================================================

SELECT
    v.id                AS video_id,
    v.title,
    v.status            AS video_status,
    s.similarity_score,
    s.hook,
    s.template_score,
    s.created_at::DATE  AS script_date
FROM scripts s
JOIN videos v ON v.id = s.video_id
WHERE s.similarity_score > 0.65
  AND s.similarity_score IS NOT NULL
ORDER BY s.similarity_score DESC;
