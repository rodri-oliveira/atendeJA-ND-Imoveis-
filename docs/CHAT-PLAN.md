# Plano do Chat WhatsApp – ND Imóveis (MVP)

## Objetivo
- **Qualificar leads** e **atender dúvidas** via WhatsApp, com **agendamento de visitas** quando houver interesse.
- Operação **24/7**. Transferência para humano ocorre **no momento do agendamento**.
- Construir em **pequenos escopos**, sempre testando com o simulador `adapter-wa/` antes de usar o número do cliente.

## Premissas e Regras
- **Janela de 24h (Meta)**: fora da janela, somente templates aprovados. MVP foca no receptivo; campanhas ativas reais ficam por último (simulador primeiro).
- **LGPD**: solicitar consentimento explícito no início. Guardar consentimento no lead.
- **Tom**: formal e amigável. Mensagens de boas-vindas e encerramento.
- **Horário do humano**: 09h–19h (configurável em tela futura). Chatbot responde 24/7.
- **Não responder**: se o lead não responder por **24h** após a última mensagem, classificar `sem_resposta_24h`. Ao retomar a conversa em qualquer momento, o lead deve ser atualizado no banco (status e timestamps) para relatórios.

## Fase 1 — Receptivo (prioridade)
### Fluxo Conversacional (alta visão)
1) Boas-vindas + consentimento LGPD.
2) Coleta obrigatória: nome, telefone, e-mail.
3) Preferências: finalidade (compra/locação), cidade/bairro, tipo (apto/casa), faixa de preço, dormitórios.
4) Retorna até 3 imóveis: foto + título + preço + bairro.
5) Pergunta se deseja agendar visita.
6) Se sim, pedir dia/horário preferidos e **transferir para humano** (registrar solicitação).
7) Encerramento com instruções e horário de atendimento humano.

### Regra de ausência de resposta
- Sem resposta por **24h**: classificar o lead como `sem_resposta_24h` e registrar evento de auditoria.
- Ao receber nova mensagem: atualizar o lead no banco e retomar o fluxo da última pergunta.

#### Lógica ao sair de `sem_resposta_24h` (determinística)
Ao receber uma mensagem do lead:
- Atualizar `last_inbound_at` e `status_updated_at`.
- Se `status == sem_resposta_24h`, recalcular o status conforme:
  1) Se houver agendamento pendente (existe registro em `re_visit_schedules` com `status=requested` para o `lead_id`): `agendamento_pendente`.
  2) Senão, se dados obrigatórios + preferências estão completos (nome, telefone, e-mail, finalidade, cidade/estado, tipo, faixa de preço ou imóvel direcionado): `qualificado`.
  3) Caso contrário: `novo`.

### Mensagens fora de escopo (padrões aprovados)
- Versão padrão (educada e diretiva):
  "Para garantir um atendimento correto, esse tema precisa do corretor responsável. Vou registrar sua dúvida e nossa equipe entrará em contato. Podemos seguir com sua busca de imóvel? Sobre a sua última pergunta, poderia me informar: {PERGUNTA_PENDENTE}?"
- Versão objetiva (quando insistir em temas não tratáveis pelo bot):
  "Esse assunto só pode ser tratado por um corretor. Posso agendar um contato? Enquanto isso, consigo avançar com sua preferência: {PERGUNTA_PENDENTE}?"

### Estados/Status do Lead (no BD)
- `novo` → `qualificado` → `agendamento_pendente` → `agendado`.
- Ramificação de ausência: `sem_resposta_24h`.
- Campo no lead: `status` (string) e `consent_lgpd` (bool).

### Modelagem — evoluções confirmadas (sem redundância)
- `status` (enum): `novo`, `qualificado`, `agendamento_pendente`, `agendado`, `sem_resposta_24h`.
- `last_inbound_at`, `last_outbound_at`, `status_updated_at` (datetime).
- `property_interest_id` (FK opcional para `re_properties`) — identifica lead direcionado a um imóvel.
- Preferências denormalizadas para filtros: `finalidade`, `tipo`, `cidade`, `estado`, `bairro`, `dormitorios`, `preco_min`, `preco_max`.
- `contact_id` (FK opcional para `contacts`) — integra com conversas, respeita `suppressed_contacts`.
- Manter `preferences` (JSON) como fonte completa das preferências.

### Dados mínimos a persistir
- Lead: nome, telefone, e-mail, consentimento, preferências (JSON), status, timestamps.
- Eventos: `lead.created`, `lead.updated`, `inquiry.created`, `visit.requested`, `followup.sent`.

### Endpoints/Serviços utilizados
- `POST /re/leads` (criar lead c/ consentimento e preferências).
- `GET /re/imoveis` (com filtros) e `GET /re/imoveis/{id}/detalhes`.
- `POST /conversation/events` (ou tabela equivalente) para auditar fluxo.

### Critérios de Aceite (Fase 1)
- Coleta de dados obrigatórios com validação e consentimento salvo.
- Regra de 24h registra evento e altera status para `sem_resposta_24h`; ao novo contato, atualizar lead e retomar fluxo.
- Retorno de imóveis com conteúdo mínimo (foto/título/preço/bairro).
- Solicitação de visita gera evento e notifica equipe (simulação no MVP).
- Testes passando (unitários e de fluxo com simulador).

## Fase 2 — Ativo/Campanhas (após receptivo)
### Tela de Campanhas (frontend)
- Filtros: **status do lead**, finalidade, tipo, cidade/estado, **bairro**, faixa de preço, dormitórios, e flag **direcionado** (com/sem `property_interest_id`).
- Ação: **Ativar campanha** (no simulador) para o conjunto filtrado.
- MVP com simulador; produção exigirá **templates** e aprovação no Meta.

### Critérios de Aceite (Fase 2)
- Tela única de campanhas com filtros e preview de alcance.
- Disparo simulado via `adapter-wa/` com logs e auditoria por lead.
- Rate limit respeitado.

## Testes e Validação
- **Backend**: pytest para regras (consentimento, status, follow-up, filtros de imóveis).
- **Simulador `adapter-wa/`**: cenários de conversas do fluxo (boas-vindas, coleta, sugestões, agendamento, follow-ups).
- **Frontend**: testes de UI essenciais (render, filtros e ação de campanha) e validação manual.

## Métricas e Relatórios
- Dashboard: conversas/dia, leads por status, taxa de qualificação, solicitações de visita.
- Relatórios por e-mail: alertas configuráveis (ex.: agendamento solicitado, volume diário).
- Notificação WhatsApp da equipe: somente quando lead fornecer dia/horário para visita.

## Configurações (MVP)
- Horário humano (09h–19h) — tela de ajustes futura.
- Flags: `WINDOW_24H_ENABLED`, `WA_RATE_LIMIT_*`, `RE_READ_ONLY` (produção), `DEFAULT_TENANT_ID`.

## Roadmap Resumido
- F1. Receptivo + simulador + testes → produção receptivo.
- F2. Tela de campanhas (simulador), métricas e relatórios.
- F3. Templates Meta (campanhas reais) + notificações para equipe.
- F4. Integrações (CRM/e-mail), melhorias e escalabilidade.

## Dúvidas Abertas
- Texto exato do consentimento LGPD (padrão institucional do cliente?).
- Tipos de e-mail/alertas desejados (evento e periodicidade).
- Lista final de **status** aceitos no lead (confirmar nomenclaturas acima).
- Frases/casos fora de escopo — mensagens oficiais desejadas.

## Referências
- `adapter-wa/` (simulador WhatsApp) — usar em ambiente local.
- `app/domain/realestate/` e `app/api/routes/` — endpoints de imóveis e leads.
- Políticas Meta: janela 24h e templates.
