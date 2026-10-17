from app.tasks.celery_app import celery_app
from app.tasks import background
from app.utils.logger import logger

if __name__ == "__main__":
    logger.info("Celery worker starting")
    try:
        celery_app.worker_main([
            "worker",
            "--loglevel=info",
            "--concurrency=1",
            "--pool=solo"
        ])
    except KeyboardInterrupt:
        pass