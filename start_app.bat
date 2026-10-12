@echo off
echo Starting SERP API Environment...

echo 1. Starting Redis via Docker...
docker-compose up -d

echo 2. Starting Celery Worker...
:: Added :celery_app so it finds the correct variable in the file
start "Celery Worker" cmd /k "python -m celery -A app.core.celery_app:celery_app worker --loglevel=info -P solo"

echo 3. Starting FastAPI Server...
start "FastAPI Server" cmd /k "python -m uvicorn app.main:app --reload --port 8000"

echo All services are booting up! You can close this main window.