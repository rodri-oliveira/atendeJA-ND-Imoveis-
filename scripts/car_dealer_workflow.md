# Fluxo profissional (car_dealer) — onboarding e manutenção

## Objetivo
Evitar retrabalho e risco em produção separando claramente:
- validação (preview)
- mudança de código (adapters/extractor)
- deploy
- ingestão (persistência)
- limpeza/reprocessamento

Garantir um processo repetível para onboard de novos clientes do nicho carro, com:
- extração consistente (preço, km, ano, marca/modelo, acessórios)
- mídia (fotos) corretamente associada
- CRUD de admin funcionando para correções manuais

## Regras
- Nunca “gravar no banco e depois ajustar o extractor”.
- Primeiro: preview + ajuste do código + deploy.
- Depois: ingestão que grava no DB.
- Se o site mudar, sempre repetir o preview antes de rodar nova ingestão.
- Se houver falhas de fotos, prefira corrigir via UI (admin) e/ou reprocessar.

## Passo a passo (novo cliente)

### 1) Preview (sem DB)
Executar preview para uma base_url e inspecionar:
- price/km/year/make/model
- accessories
- images

Comando:
- python scripts/vehicles_preview.py --base-url "<BASE_URL>" --sample 5 --pretty

Critério mínimo de qualidade:
- coverage >= 0.7
- images_count >= 3

Observações:
- Se a URL do cliente é do tipo ClickGarage, normalmente já é suportada.
- Se for SPA/JS pesado e o preview vier “vazio”, considerar um adapter específico ou estratégia alternativa.

### 2) Ajustar extractor/adapters
- Se site for ClickGarage (ou similar), manter parser de labels.
- Se site for SPA/JS pesado e preview não retorna campos, considerar Plano B (headless) ou adapter específico.

Arquivos principais:
- app/domain/vehicles_ingestion/extractor.py
- app/domain/vehicles_ingestion/discovery.py
- app/domain/vehicles_ingestion/service.py

### 3) Deploy
- Fazer commit + deploy do backend.
- Validar em staging quando existir.

### 4) Ingestão (grava no DB)
Comando:
- python scripts/vehicles_ingest.py --tenant-id <TENANT_ID> --base-url "<BASE_URL>" --max-listings 30 --max-listing-pages 4

Notas:
- A ingestão faz upsert via external_key (por URL normalizada), então rodar de novo atualiza itens existentes.

### 5) Limpeza de mídia (se necessário)
Se a capa/galeria estiver puxando logo/banner:
- python scripts/vehicles_media_cleanup.py --tenant-id <TENANT_ID>

Quando usar:
- O cliente tem imagens “globais” (logo/banner) sendo incluídas pelo HTML.
- O card está pegando imagem errada como capa.

### 6) Validação na UI
- /catalog/vehicles
- /catalog/vehicles/:id

Seções admin:
- Cadastrar: /catalog/vehicles/novo
- Editar: /catalog/vehicles/:id/editar

Checklist:
- cards mostram foto de carro (não banner)
- detalhe mostra preço/km/ano/marca/modelo
- acessórios aparecem como chips
- CRUD (novo/editar/arquivar/excluir) funcionando para admin

Checklist de mídia (fotos):
- Fotos aparecem na lista (thumb)
- Fotos aparecem no detalhe (galeria)
- Admin consegue remover foto ruim e adicionar nova

### 7) Reprocessamento
- Rodar nova ingestão (o upsert atualiza itens existentes via external_key)
- Se necessário, rodar cleanup novamente

Opcional (para itens já existentes no DB):
- python scripts/vehicles_reprocess_existing.py --tenant-id <TENANT_ID>

Use quando:
- Melhoramos o extractor e queremos enriquecer veículos já ingeridos.
- Existem veículos com campos faltando (ano/km/marca/modelo) e queremos reextrair.

---

## Operação diária (admin)

### Correções manuais comuns
- Ajustar título/descrição/preço/ano/km/marca/modelo/acessórios via editar.
- Arquivar (soft delete) quando veículo não está mais disponível.
- Exclusão permanente (hard delete) quando precisa remover item + mídias + referências.

### Fotos por URL: como usar
O campo de fotos por URL aceita apenas URL direta do arquivo de imagem.

Exemplos de URL válida:
- termina com .jpg / .jpeg / .png / .webp
- ou possui a extensão antes de ?/# (ex.: foto.jpg?width=1200)

Exemplos de URL inválida (não renderiza em <img>):
- URL da página do anúncio (ex.: /veiculos/...#gallery)

Procedimento recomendado:
- Abrir a foto no site do cliente.
- Botão direito na foto -> "Copiar endereço da imagem".
- Colar a URL direta no campo de fotos.

---

## Troubleshooting

### Fotos "adicionam" mas não aparecem
Causas típicas:
- URL colada é da página do anúncio (HTML), não do arquivo de imagem.
- O site bloqueia hotlink (menos comum quando a URL é direta).

Como diagnosticar:
- No Editar, abrir a URL da foto em nova aba.
- Se abrir a página do anúncio, a URL está errada para uso como imagem.

### 401 em /api/auth/me
Indica que o admin não está autenticado.
Verifique:
- Login
- token no localStorage
- headers X-Tenant-Id / Authorization enviados pelo apiFetch
