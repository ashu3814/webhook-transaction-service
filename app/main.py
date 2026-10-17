from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.database import Base, engine
from app.routers import health, webhooks, transactions
from app.utils.logger import logger

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Webhook Service",
    version="1.0.0",
    description="Transaction webhook processor with background job handling"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(webhooks.router)
app.include_router(transactions.router)


@app.on_event("startup")
async def startup_event():
    logger.info(f"🚀 Webhook Service Started | env={settings.API_ENV}")
    logger.info(f"📍 Running on {settings.API_HOST}:{settings.API_PORT}")
    logger.info(f"🗄️  Database: PostgreSQL | 📨 Queue: CloudAMQP")


@app.on_event("shutdown")
async def shutdown_event():
    logger.info("🛑 Webhook Service Stopped")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=(settings.API_ENV == "development")
    )