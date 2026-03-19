web: PYTHONPATH=src gunicorn web.app:app --bind 0.0.0.0:${PORT:-8000} --workers 1 --worker-class uvicorn.workers.UvicornWorker --timeout 120 --keep-alive 5 --preload
