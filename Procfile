worker: celery -A cuidarjuntos worker --concurrency=2 -l info
beat: celery -A cuidarjuntos beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler
