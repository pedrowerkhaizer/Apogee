---
description: Scaffolda um novo agente LLM com assinatura tipada, prompt separado, tracing LangSmith, registro em agent_runs e exemplo de execução manual. Informe o nome e o que o agente recebe e retorna
---

Crie um novo agente LLM para o Apogee Engine seguindo estas regras:
1. Arquivo em `videoops/agents/[nome_do_agente].py`
2. Função principal com assinatura tipada (input Pydantic → output Pydantic)
3. Logging com LangSmith (@traceable)
4. Registro em `agent_runs` com tokens, custo e duração
5. Prompt em variável separada `SYSTEM_PROMPT` no topo do arquivo
6. Docstring explicando o que o agente faz, input esperado e output
7. Inclua um bloco `if __name__ == "__main__"` com exemplo de execução manual

Agente a criar: [DESCREVA AQUI]