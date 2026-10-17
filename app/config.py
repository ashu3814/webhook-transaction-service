from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql://postgres:password@localhost:5432/webhook_db"
    RABBITMQ_URL: str = "amqp://guest:guest@localhost:5672//"
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    API_ENV: str = "development"
    CELERY_BROKER_URL: str = "amqp://guest:guest@localhost:5672//"
    CELERY_RESULT_BACKEND: str = "db+postgresql://postgres:password@localhost:5432/webhook_db"
    
    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()