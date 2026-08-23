import uuid

import django.core.validators
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

import apps.common.validators


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Monitor",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4, editable=False, primary_key=True, serialize=False
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("name", models.CharField(max_length=100)),
                (
                    "url",
                    models.URLField(
                        max_length=2048, validators=[apps.common.validators.validate_monitor_url]
                    ),
                ),
                (
                    "method",
                    models.CharField(
                        choices=[("GET", "GET"), ("HEAD", "HEAD"), ("POST", "POST")],
                        default="GET",
                        max_length=4,
                    ),
                ),
                (
                    "expected_status",
                    models.PositiveSmallIntegerField(
                        default=200,
                        validators=[
                            django.core.validators.MinValueValidator(100),
                            django.core.validators.MaxValueValidator(599),
                        ],
                    ),
                ),
                (
                    "interval_seconds",
                    models.PositiveIntegerField(
                        choices=[
                            (60, "60"),
                            (120, "120"),
                            (300, "300"),
                            (600, "600"),
                            (900, "900"),
                            (1800, "1800"),
                            (3600, "3600"),
                        ],
                        default=300,
                    ),
                ),
                (
                    "timeout_seconds",
                    models.PositiveSmallIntegerField(
                        default=10,
                        validators=[
                            django.core.validators.MinValueValidator(1),
                            django.core.validators.MaxValueValidator(30),
                        ],
                    ),
                ),
                ("headers", models.JSONField(blank=True, default=dict)),
                (
                    "failure_threshold",
                    models.PositiveSmallIntegerField(
                        default=2,
                        validators=[
                            django.core.validators.MinValueValidator(1),
                            django.core.validators.MaxValueValidator(10),
                        ],
                    ),
                ),
                (
                    "success_threshold",
                    models.PositiveSmallIntegerField(
                        default=1,
                        validators=[
                            django.core.validators.MinValueValidator(1),
                            django.core.validators.MaxValueValidator(10),
                        ],
                    ),
                ),
                ("is_enabled", models.BooleanField(default=True)),
                (
                    "health_status",
                    models.CharField(
                        choices=[("NEW", "New"), ("UP", "Up"), ("DOWN", "Down")],
                        default="NEW",
                        max_length=4,
                    ),
                ),
                ("consecutive_failures", models.PositiveIntegerField(default=0)),
                ("consecutive_successes", models.PositiveIntegerField(default=0)),
                ("last_checked_at", models.DateTimeField(blank=True, null=True)),
                ("next_check_at", models.DateTimeField()),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="monitors",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
                "indexes": [
                    models.Index(
                        fields=["is_enabled", "next_check_at"], name="monitor_dispatch_idx"
                    ),
                    models.Index(fields=["user", "created_at"], name="monitor_user_created_idx"),
                ],
                "constraints": [
                    models.CheckConstraint(
                        condition=models.Q(
                            ("expected_status__gte", 100), ("expected_status__lte", 599)
                        ),
                        name="monitor_expected_status_range",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(
                            ("timeout_seconds__gte", 1), ("timeout_seconds__lte", 30)
                        ),
                        name="monitor_timeout_range",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(
                            ("failure_threshold__gte", 1), ("failure_threshold__lte", 10)
                        ),
                        name="monitor_failure_threshold_range",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(
                            ("success_threshold__gte", 1), ("success_threshold__lte", 10)
                        ),
                        name="monitor_success_threshold_range",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(("timeout_seconds__lt", models.F("interval_seconds"))),
                        name="monitor_timeout_lt_interval",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(
                            ("interval_seconds__in", (60, 120, 300, 600, 900, 1800, 3600))
                        ),
                        name="monitor_interval_allowed_values",
                    ),
                ],
            },
        ),
    ]
