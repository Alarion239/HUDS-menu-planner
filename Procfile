web: sh -c "python manage.py migrate && python manage.py collectstatic --noinput && python manage.py create_default_superuser && gunicorn --bind 0.0.0.0:$PORT --workers 3 huds_project.wsgi:application"
worker: celery -A huds_project worker --loglevel=info --concurrency=3
beat: celery -A huds_project beat --loglevel=info --scheduler django_celery_beat.schedulers:DatabaseScheduler
bot: python manage.py run_telegram_bot