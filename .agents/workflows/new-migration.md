---
description: Gera arquivo SQL numerado para o Supabase com comentário de intenção, IF NOT EXISTS, ALTER TABLE se necessário, índices ivfflat para vetores e rollback comentado. Informe a mudança de schema.
---

Crie uma migration SQL para o Supabase seguindo estas regras:
1. Arquivo em `migrations/[NNN]_[descricao].sql` onde NNN é o próximo número sequencial
2. Inclua comentário no topo explicando o motivo da migration
3. Use `IF NOT EXISTS` em CREATE statements
4. Se alterar tabela existente, use ALTER TABLE, nunca recriar
5. Inclua índices necessários para queries de similaridade (ivfflat se for VECTOR)
6. Adicione script de rollback comentado no final do arquivo

Mudança a implementar: [DESCREVA AQUI]