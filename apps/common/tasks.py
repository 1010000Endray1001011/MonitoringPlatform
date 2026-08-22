import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(name="apps.common.tasks.ping")
def ping() -> str:
    logger.info("pong")
    return "pong"
