# Contratos da API (PT user-facing + compatibilidade)

Este documento descreve padrões de contrato (DTOs) e envelope de erro do backend.

## 1) Princípios

- **User-facing em PT**: chaves que representam conceitos de negócio exibidos ao usuário final devem ser em português (ex.: `titulo`, `preco`, `cidade`).
- **Compatibilidade PT/EN em inputs**: quando houver integrações/clients legados, os DTOs podem aceitar aliases em inglês (ex.: `title`, `price`, `city`).
- **Chaves técnicas podem permanecer em EN**: campos de infraestrutura/integração podem permanecer em inglês por boa prática e compatibilidade (ex.: `tenant_id`, `external_id`, `ref_code`, `access_token`).

---

## 2) Envelope padrão de erro

Todas as respostas de erro devem seguir o formato:

```json
{
  "error": {
    "code": "...",
    "message": "...",
    "details": null
  }
}
```

- **`error.code`**: identificador estável (snake_case), usado pelo front para tratar casos específicos.
- **`error.message`**: mensagem curta e segura (PT preferencial quando user-facing).
- **`error.details`**: opcional; usar quando ajudar diagnóstico (ex.: validação 422 ou erros upstream).

### Como gerar erros corretamente

- Para erros simples, use:

```py
raise HTTPException(status_code=404, detail="tenant_not_found")
```

- Para erros com mensagem e/ou detalhes:

```py
raise HTTPException(
    status_code=400,
    detail={"code": "validation_error", "message": "Requisição inválida.", "details": {...}},
)
```

### Observações

- O handler global converte `HTTPException.detail` para o envelope acima.
- Para `RequestValidationError` (422), `details` contém a lista de erros do Pydantic.

---

## 3) Imóveis (Real Estate)

### 3.1 Respostas (user-facing em PT)

`ImovelSaida` e `ImovelDetalhes` usam chaves em português:

- `titulo`, `descricao`, `tipo`, `finalidade`, `preco`
- `cidade`, `estado`, `bairro`
- `dormitorios`, `banheiros`, `suites`, `vagas`
- `imagens`: lista de itens com `url`, `is_capa`, `ordem`

Campo adicional:
- `url_capa`: serialização do campo interno `cover_image_url`.

### 3.2 Inputs aceitam PT/EN (aliases)

#### `ImovelCriar` / `ImovelAtualizar`

Aceita (exemplos):

- `titulo` ou `title`
- `descricao` ou `description`
- `tipo` ou `type`
- `finalidade` ou `purpose`
- `preco` ou `price`
- `cidade` ou `city`
- `estado` ou `state`
- `bairro` ou `neighborhood`
- `endereco_json` ou `address_json`
- `dormitorios` ou `bedrooms`
- `banheiros` ou `bathrooms`
- `vagas` ou `parking_spots`

#### `ImagemCriar`

Aceita:

- `is_capa` ou `is_cover`
- `ordem` ou `sort_order`
- `storage_key` ou `storageKey`

---

## 4) Leads

### 4.1 Respostas (user-facing em PT)

`LeadOut` usa:

- `nome`, `telefone`, `origem`, `preferencias`, `consentimento_lgpd`

### 4.2 Inputs aceitam PT/EN (aliases)

- `nome` / `name`
- `telefone` / `phone`
- `origem` / `source`
- `preferencias` / `preferences`
- `consentimento_lgpd` / `consent_lgpd`

---

## 5) Campos técnicos (mantidos em inglês)

Por serem chaves de integração/infra ou identificadores externos, permanecem em inglês:

- `tenant_id`
- `external_id`
- `ref_code`
- `access_token`
- (outros semelhantes)

---

## 6) Rotas técnicas (Auth / Super Admin)

As rotas de **autenticação** e **super admin** são consideradas **técnicas/operacionais**.

- As **chaves** tendem a permanecer em inglês por estabilidade e compatibilidade (ex.: `access_token`, `token_type`, `tenant_id`, `is_active`, `phone_number_id`).
- A tradução para português deve ocorrer **na UI** (labels e textos), não por renome de campos na API.
- Erros dessas rotas devem seguir o **envelope padrão** descrito na seção 2.
