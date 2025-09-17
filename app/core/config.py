from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # App
    APP_ENV: str = "dev"  # dev|prod|test
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    DEFAULT_TENANT_ID: str = "default"

    # WhatsApp Cloud API
    WA_VERIFY_TOKEN: str = "changeme"
    WA_TOKEN: str = ""
    WA_PHONE_NUMBER_ID: str = ""
    WA_API_BASE: str = "https://graph.facebook.com/v20.0"
    # Provider de mensageria: meta|twilio (usar 'meta' por padrão)
    WA_PROVIDER: str = "meta"
    # Optional: HMAC secret to validate webhook signatures (X-Hub-Signature-256)
    WA_WEBHOOK_SECRET: str = ""

    # Database
    POSTGRES_HOST: str = "postgres"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "atendeja"
    POSTGRES_USER: str = "atendeja"
    POSTGRES_PASSWORD: str = "atendeja"
    # Optional: full database URL override (e.g., sqlite:///./test.db). When set, it takes precedence.
    DATABASE_URL_OVERRIDE: str = ""

    # Redis / Celery
    REDIS_HOST: str = "redis"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0

    # Chatbot – boas práticas
    # Janela de sessão: mensagens livres somente dentro de 24h desde a última mensagem do cliente
    WINDOW_24H_ENABLED: bool = True
    WINDOW_24H_HOURS: int = 24
    # Rate limit
    WA_RATE_LIMIT_PER_CONTACT_SECONDS: int = 2  # 1 msg a cada 2s por contato
    WA_RATE_LIMIT_GLOBAL_PER_MINUTE: int = 60   # teto global por tenant/minuto

    # MCP (Model Context Protocol) – autenticação simples para /mcp/execute
    MCP_API_TOKEN: str = ""  # quando definido, exigir Bearer <token> no endpoint MCP

    # Imóveis somente leitura (produção)
    RE_READ_ONLY: bool = False

    # Auth (login do sistema)
    AUTH_JWT_SECRET: str = "changeme"
    AUTH_JWT_EXPIRE_MINUTES: int = 60
    AUTH_SEED_ADMIN_EMAIL: str = ""
    AUTH_SEED_ADMIN_PASSWORD: str = ""

    @property
    def DATABASE_URL(self) -> str:
        if self.DATABASE_URL_OVERRIDE:
            return self.DATABASE_URL_OVERRIDE
        return (
            f"postgresql+psycopg2://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @property
    def REDIS_URL(self) -> str:
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore


settings = get_settings()
