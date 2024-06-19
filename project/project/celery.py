from __future__ import absolute_import, unicode_literals
import os
from celery import Celery
from celery.schedules import crontab

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'project.settings')

app = Celery('project')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

app.conf.beat_schedule = {
    'save-images-every-5-minutes': {
        'task': 'app.tasks.save_images_task',
        'schedule': crontab(minute='*/5'),
    },
    'update-ndvi-values-every-week': {
        'task': 'app.tasks.update_ndvi_values',
        'schedule': crontab(hour=0, minute=0, day_of_week='monday'),
    },
}