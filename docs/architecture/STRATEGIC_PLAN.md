# Strategic Architecture Plan: Multi-Tenant Chatbot SaaS

## 1. Vision
Transform the current domain-specific chatbot into a generic, niche-agnostic platform capable of supporting multiple business types (Real Estate, Car Dealer, etc.) with minimal code changes.

## 2. Core Pillars

### A. Niche-Agnostic Engine
The `FlowEngine` will be refactored to remove all domain-specific knowledge.
- **Generic Nodes**: All nodes will use standard types (`message`, `choice`, `capture`).
- **Action Registry**: Specialized logic (like database searches) will be registered as external actions.
- **State Management**: Schema-less state storage to support different business entities.

### B. Natural Language Flow Creation
A new layer will be added to the Admin UI to allow "Talking to the Bot to create the Bot".
- **Instruction to JSON**: A deterministic parser that maps Portuguese commands to flow configurations.
- **Templates**: Pre-defined skeletons for common niches.

### C. Guardrails as a Service
Standard behaviors that are automatically applied to every bot:
- **Universal Keywords**: `menu`, `reiniciar`, `falar com atendente`.
- **Automatic Fallback**: A `não_entendi` state that triggers LLM classification if deterministic rules fail.

## 3. Implementation Roadmap

### Phase 1: Engine Sanitization
- Extract domain-specific handlers from `flow_engine.py` into `app/domain/<niche>/actions.py`.
- Implement a generic `executar_acao` node type.

### Phase 2: Command Parser
- Create the `app/services/chatbot_command_parser.py`.
- Integrate with the Admin UI to allow text-based flow generation.

### Phase 3: Dynamic LLM Prompts
- Refactor `llm_service.py` to generate prompts based on the current flow's available routes instead of hardcoded strings.

## 4. Preservation Policy (ND Imóveis)
The existing real estate implementation is the project's benchmark. Every update to the engine must be validated against the `real_estate` domain to ensure zero regression.
