# Correções Implementadas - Fluxo de Busca Assistida

## Problema Identificado
O fluxo de busca assistida estava **travando** em `awaiting_visit_decision` e depois em `awaiting_phone_input`, impedindo a criação do agendamento.

## Correções Aplicadas

### 1. ✅ `handle_visit_decision` (linha 946)
**Problema**: Não detectava "Quero agendar" como intenção de agendamento
**Solução**: Adicionada detecção de palavras positivas ANTES de outras verificações
```python
positive_responses = ["sim", "quero", "agendar", "marcar", "visita", "correto", "ok", "confirmo"]
if any(word in text_lower for word in positive_responses):
    # Ir direto para confirmação de telefone
```

### 2. ✅ `handle_phone_confirmation` (linha 240)
**Problema**: "Está correto" não era detectado como confirmação positiva
**Solução**: Adicionada lista de palavras positivas
```python
positive_words = ["sim", "correto", "ok", "confirmo", "esse mesmo", "está correto", "esta correto", "yes", "certo"]
is_positive = any(word in text_lower for word in positive_words) or detect.detect_yes_no(text) == "yes"
```

### 3. ✅ `handle_phone_input` (linha 258)
**Problema**: Quando usuário dizia "Está correto", sistema tentava validar como telefone e falhava
**Solução**: Detectar confirmação positiva ANTES de validar telefone
```python
positive_words = ["sim", "correto", "ok", "confirmo", "esse mesmo", "está correto", "esta correto"]
if any(word in text_lower for word in positive_words):
    # Usar telefone já salvo e avançar
```

### 4. ✅ `handle_visit_time` (linha 301)
**Problema**: Busca de lead por telefone não considerava formato com @c.us
**Solução**: Buscar com OR para ambos os formatos
```python
lead = self.db.query(Lead).filter(
    (Lead.phone == phone) | (Lead.phone == sender_id)
).first()
```

### 5. ✅ `handle_visit_time` - property_id
**Problema**: Não buscava property_id do fluxo de busca assistida
**Solução**: Buscar de ambos os fluxos
```python
property_id = state.get("directed_property_id") or state.get("interested_property_id")
```

### 6. ✅ Remoção de estágios obsoletos
**Problema**: `collecting_name` e `collecting_email` ainda estavam no código
**Solução**: Removidos completamente (não são mais necessários)

## Fluxo Esperado Agora

1. ✅ Usuário: "Olá" → `start`
2. ✅ Usuário: "Sim" (LGPD) → `awaiting_name`
3. ✅ Usuário: "Roberto Silva" → `awaiting_has_property_in_mind`
4. ✅ Usuário: "Não" → `awaiting_purpose`
5. ✅ Usuário: "Comprar" → `awaiting_type`
6. ✅ Usuário: "Apartamento" → `awaiting_price_min`
7. ✅ Usuário: "200000" → `awaiting_price_max`
8. ✅ Usuário: "300000" → `awaiting_bedrooms`
9. ✅ Usuário: "2" → `awaiting_city`
10. ✅ Usuário: "Suzano" → `awaiting_neighborhood`
11. ✅ Usuário: "Não" → `searching` → `showing_property` → `awaiting_property_feedback`
12. ✅ Usuário: "1" (ver detalhes) → `awaiting_visit_decision`
13. ✅ Usuário: "Quero agendar" → `awaiting_phone_confirmation` ← **CORRIGIDO**
14. ✅ Usuário: "Está correto" → `awaiting_visit_date` ← **CORRIGIDO**
15. ✅ Usuário: "Amanhã" → `awaiting_visit_time`
16. ✅ Usuário: "10h" → Cria lead + agendamento ← **CORRIGIDO**

## Dados Salvos no Lead

- ✅ Nome (do início da conversa)
- ✅ Telefone (do sender_id)
- ✅ Status: "agendado"
- ✅ Property interest ID
- ✅ Código do imóvel (ref_code)
- ✅ Finalidade (do state)
- ✅ Tipo (do state)
- ✅ Cidade (do state)
- ✅ Dormitórios (do state)
- ✅ Preço min/max (do state)
- ✅ Last inbound at (timestamp)

## Teste Recomendado

Execute: `poetry run python test_busca_simples.py`

Verifique:
1. Lead criado com todos os dados
2. Agendamento criado
3. Status = "agendado"
4. Código do imóvel preenchido
