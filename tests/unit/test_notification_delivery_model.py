import pytest
from django.db import IntegrityError, transaction

from apps.incidents.models import Incident
from apps.notifications.models import NotificationDelivery
from tests.factories import IncidentFactory, NotificationChannelFactory

pytestmark = pytest.mark.django_db


def test_unique_constraint_rejects_a_duplicate_event_for_the_same_channel():
    incident = IncidentFactory(status=Incident.Status.OPEN)
    channel = NotificationChannelFactory()
    NotificationDelivery.objects.create(
        incident=incident,
        channel=channel,
        event_type=NotificationDelivery.EventType.INCIDENT_OPENED,
    )

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            NotificationDelivery.objects.create(
                incident=incident,
                channel=channel,
                event_type=NotificationDelivery.EventType.INCIDENT_OPENED,
            )


def test_the_same_incident_and_channel_can_have_both_event_types():
    incident = IncidentFactory(status=Incident.Status.RESOLVED)
    channel = NotificationChannelFactory()

    NotificationDelivery.objects.create(
        incident=incident,
        channel=channel,
        event_type=NotificationDelivery.EventType.INCIDENT_OPENED,
    )
    NotificationDelivery.objects.create(
        incident=incident,
        channel=channel,
        event_type=NotificationDelivery.EventType.INCIDENT_RESOLVED,
    )

    assert NotificationDelivery.objects.filter(incident=incident, channel=channel).count() == 2


def test_str_shows_channel_incident_and_status():
    incident = IncidentFactory()
    channel = NotificationChannelFactory()
    delivery = NotificationDelivery.objects.create(
        incident=incident,
        channel=channel,
        event_type=NotificationDelivery.EventType.INCIDENT_OPENED,
    )

    text = str(delivery)

    assert str(channel.id) in text
    assert str(incident.id) in text
    assert "PENDING" in text
