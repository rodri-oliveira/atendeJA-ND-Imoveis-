## Visão geral
Guia rápido para restaurar o projeto em outra máquina (repo privado). Abrange backend (FastAPI/Poetry), frontend (Vite/React), banco/Redis e WA adapter.

### Requisitos
- Python 3.11+ (Poetry instalado)  
- Node 18+  
- Docker e Docker Compose (para subir serviços)  
- Postgres 14+ (se usar local)  
- Redis 6+ (se usar local)

### Estrutura
- `app/` backend FastAPI
- `frontend/ui/` Vite+React
- `adapter-wa/` adaptador WhatsApp (opcional/WA)
- `docker-compose.yml` serviços rápidos (db/redis/minio?)
- `.env.example` variáveis de ambiente (copiar para `.env`)

## Passo a passo (mínimo)
1. **Clonar**  
   ```bash
   git clone <repo-privado>
   cd atendeJA-ND-Imoveis-
   ```

2. **Criar `.env` a partir do exemplo**  
   ```bash
   cp .env.example .env
   # Ajustar senhas/segredos: POSTGRES_PASSWORD, AUTH_JWT_SECRET, WA_* se usar WhatsApp
   ```

3. **Subir dependências via Docker (db/redis)**  
   ```bash
   docker compose up -d
   # serviços: postgres em 5432, redis em 6379 (ajustar .env se necessário)
   ```

4. **Backend (Poetry)**  
   ```bash
   pip install poetry
   poetry install
   poetry run alembic upgrade head   # migrações
   poetry run uvicorn app.main:app --reload
   ```
   - Config principal: `.env` (APP_ENV, DATABASE_URL_OVERRIDE ou POSTGRES_*, REDIS_*).
   - Seeds opcionais: `AUTH_SEED_ADMIN_EMAIL`/`AUTH_SEED_ADMIN_PASSWORD`.

5. **Frontend (Vite/React)**  
   ```bash
   cd frontend/ui
   npm install
   npm run dev
   ```
   - Usa por padrão backend em `localhost:8000` se configurado no código/api proxy (ajustar se necessário).

6. **Adapter WA (opcional)**  
   ```bash
   cd adapter-wa
   npm install
   npm run start   # requer WA_TOKEN/WA_PHONE_NUMBER_ID se for usar WhatsApp
   ```

## Checks rápidos
- `docker compose ps` → postgres/redis up  
- `poetry run pytest` (tests backend)  
- `npm test` (se aplicável no frontend)  
- Abrir `http://localhost:5173` (Vite) / `http://localhost:8000/docs` (FastAPI docs)

## Observações de segurança
- Não commitar `.env`; use `.env.example` (já no repo).  
- Trocar `CHANGE_ME` e senhas default.  
- WA tokens e segredos devem ser fornecidos manualmente.

## Comandos úteis
- Parar serviços: `docker compose down`  
- Reset DB dev: drop DB ou recriar volume docker.  
- Rodar servidor backend com reload: `poetry run uvicorn app.main:app --reload --port 8000`
