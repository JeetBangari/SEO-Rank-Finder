#!/usr/bin/env bash
# Start the Celery worker in the background
celery -A app.core.celery_app worker --loglevel=info &

# Start the FastAPI web server in the foreground
uvicorn app.main:app --host 0.0.0.0 --port $PORT