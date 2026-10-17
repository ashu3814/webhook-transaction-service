from app.tasks.celery_app import celery_app
from app.tasks import background
from app.utils.logger import logger

if __name__ == "__main__":
    logger.info("🚀 Celery Worker Starting")
    logger.info("📌 Broker: CloudAMQP | Backend: PostgreSQL | Pool: solo")
    try:
        celery_app.worker_main([
            "worker",
            "--loglevel=info",
            "--concurrency=1",
            "--pool=solo"
        ])
    except KeyboardInterrupt:
        logger.info("🛑 Celery Worker Stopped")