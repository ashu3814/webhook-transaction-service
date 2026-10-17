from app.tasks.celery_app import celery_app
from app.tasks import background

if __name__ == "__main__":
    celery_app.worker_main([
        "worker",
        "--loglevel=info",
        "--concurrency=4"
    ])