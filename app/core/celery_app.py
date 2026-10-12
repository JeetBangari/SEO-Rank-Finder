import os
from celery import Celery
from app.config import settings

# Automatically switch between Render's cloud Redis and your local Docker Redis
REDIS_URL = os.getenv("REDIS_URL", settings.REDIS_URL)

celery_app = Celery(
    "serp_worker",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=["app.tasks"]
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
)