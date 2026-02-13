"""
Celery configuration for TheKnowledgeOrbits.
"""
import os
from celery import Celery

# Set the default Django settings module to match your project structure
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')

app = Celery('TheKnowledgeOrbits')

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
# - namespace='CELERY' means all celery-related configuration keys
#   should have a `CELERY_` prefix.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Load task modules from all registered Django apps.
app.autodiscover_tasks()

# Optional: Add explicit routing if desired (but autodiscover usually works for tasks in 'tasks.py')
# app.conf.task_routes = {
#     'engines.content.tasks.*': {'queue': 'content'},
#     'engines.current_affairs.tasks.*': {'queue': 'ca'},
# }

@app.task(bind=True, ignore_result=True)
def debug_task(self):
    print(f'Request: {self.request!r}')
    