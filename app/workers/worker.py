from celery import Celery

from app.config import get_settings
from app.core.logging import configure_logging

configure_logging()

celery = Celery("agentflow", broker=get_settings().redis_url)
celery.conf.update(
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    broker_transport_options={"visibility_timeout": 900},
    task_soft_time_limit=get_settings().task_timeout + 25,
    task_time_limit=get_settings().task_timeout + 35,
)


@celery.task(name="agentflow.execute", ignore_result=True)
def run_task(task_id):
    from app.services.execution_service import execute_task

    execute_task(task_id)
