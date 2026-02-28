web: PYTHONPATH=src gunicorn src.web.app:app --bind 0.0.0.0:${PORT:-8000} --workers ${WORKERS:-2} --worker-class uvicorn.workers.UvicornWorker --timeout 120 --keep-alive 5
