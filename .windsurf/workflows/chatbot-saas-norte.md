---
description: Direção do produto (SaaS de Chatbot) — arquitetura refined, guardrails e extensibilidade
---

# Regra primordial (SaaS Moderno)

- **Engine Aganóstica**: O núcleo (`FlowEngine`) não conhece detalhes de Imóveis ou Carros.
- **Niche Handlers**: Regras de negócio vivem em módulos isolados.
- **Linguagem Natural como Interface**: Criação de fluxos via texto (Admin).
- **Código Limpo e DDD**: Modelo rico no domínio, sem "arquivos monstro".

# Objetivo
Este workflow é o “norte” para escalar o Chatbot como SaaS multi-tenant. A meta é:

- Permitir que o **dono do SaaS configure novos nichos** (Lojas de Carros, Clínicas, etc.) sem mudar o código core.
- Usar **Linguagem Natural** para que o Admin monte a estrutura do bot via interface.
- Manter o domínio de **Imóveis (ND Imóveis) funcionando** perfeitamente como caso de sucesso.

# Visão Arquitetural

## 1) Engine "Burra", Plugin "Inteligente"
A Engine de fluxo apenas orquestra estados e transições. Ações complexas como "buscar imóvel" ou "filtrar carro por preço" são chamadas via um registro de ações:
- `executar_acao(nome="real_estate.search")`
- `executar_acao(nome="car_dealer.search")`

## 2) Criador de Fluxo (Natural Language)
O Admin deve poder digitar: *"Crie um bot de agendamento com captura de telefone"* e o sistema deve gerar o JSON do fluxo automaticamente.

# Princípios de Produto

## 1) Guardrails Globais (Core)
Todo bot, independente do nicho, herda:
- `menu`, `reiniciar`, `atendente`, `nao_entendi`.

## 2) Fallback com LLM Dinâmico
A LLM não tem prompts "hardcoded" de imóveis. O prompt é gerado dinamicamente com base nas "intenções disponíveis" no fluxo do cliente.

# Fluxo de Trabalho (Anti-Regressão)

1.  **Garantia ND Imóveis**: Qualquer mudança na engine deve ser testada contra o domínio de imóveis legado.
2.  **Modularização**: Se um arquivo (como `flow_engine.py`) ultrapassa 500 linhas, ele deve ser fatiado em componentes (Ex: `TransitionManager`, `CaptureStore`).
3.  **Documentação**: Decisões de arquitetura devem ser registradas em `docs/architecture/`.
