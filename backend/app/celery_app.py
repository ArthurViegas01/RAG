"""
Configuração do Celery.
Celery processa tasks assincronamente usando Redis como message broker.
"""

from celery import Celery

from app.config import settings

# Cria instância do Celery
celery_app = Celery(
    "rag_backend",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

# Descobre automaticamente tasks definidas em app.tasks
celery_app.autodiscover_tasks(["app"])

# Configurações
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    worker_log_format="%(asctime)s %(levelname)-8s %(message)s",
    worker_task_log_format="%(asctime)s %(levelname)-8s %(message)s",
    # Evita CPendingDeprecationWarning no Celery 5.x
    broker_connection_retry_on_startup=True,
)
