"""
The Celery side of delivery — deliberately thin, same philosophy as
apps.checks.tasks: the actual logic (claiming a delivery, calling the
provider, deciding what the outcome means) lives in
apps.notifications.services and is tested without Celery at all. This
task's only job is turning a SendResult into a retry/give-up decision.
"""

import logging
import random

from celery import shared_task

from . import services
from .models import NotificationDelivery

logger = logging.getLogger(__name__)

# max_retries=4 means 5 total attempts (1 initial + 4 retries) before a
# temporary failure is finally given up on as FAILED.
MAX_RETRIES = 4


def _backoff_seconds(retry_number: int) -> int:
    """Exponential backoff with jitter: roughly 1m, 2m, 4m, 8m. The jitter
    (up to 10% extra) exists so a batch of deliveries that all failed at
    the same moment — one provider outage affecting several channels —
    don't all retry at exactly the same moment again."""
    base = 60 * (2**retry_number)
    return int(base + random.uniform(0, base * 0.1))


@shared_task(
    name="apps.notifications.tasks.deliver_notification",
    bind=True,
    max_retries=MAX_RETRIES,
    # Safe to redeliver: attempt_delivery's conditional UPDATE (PENDING ->
    # SENDING) means a duplicate execution of this exact task finds
    # nothing left to do rather than sending a second message. That's what
    # makes acks_late=True the right call here, unlike run_check — losing
    # this task outright would mean an incident nobody gets told about,
    # which is worse than the (already-guarded-against) risk of a
    # redelivery.
    acks_late=True,
)
def deliver_notification(self, delivery_id) -> None:
    try:
        delivery = NotificationDelivery.objects.select_related("channel", "incident__monitor").get(
            id=delivery_id
        )
    except NotificationDelivery.DoesNotExist:
        return

    result = services.attempt_delivery(delivery=delivery)
    if result is None or result.success or result.permanent_error:
        # Nothing left to do, it worked, or retrying would be pointless —
        # attempt_delivery already recorded the right terminal status (or
        # left the row exactly as some other worker's attempt did).
        return

    if self.request.retries >= self.max_retries:
        services.mark_delivery_failed(
            delivery=delivery,
            error_message=result.error_message or "delivery failed after all retries",
        )
        return

    countdown = result.retry_after or _backoff_seconds(self.request.retries)
    raise self.retry(
        exc=RuntimeError(result.error_message or "temporary delivery failure"),
        countdown=countdown,
    )
