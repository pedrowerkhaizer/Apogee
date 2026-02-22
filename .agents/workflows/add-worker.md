---
description: Cria worker RQ com chamada ao agente correspondente, tratamento de erro com retry, registro de falha em agent_runs e exemplo de enfileiramento. Informe o agente que o worker vai executar.
---

Crie um worker RQ para o Apogee Engine:
1. Arquivo em `videoops/workers/[nome_worker].py`
2. Função de job que chama o agente correspondente
3. Tratamento de erro com retry e registro de falha em `agent_runs`
4. Enfileiramento na queue correta
5. Exemplo de como enfileirar o job em um script separado

Worker a criar: [DESCREVA AQUI]