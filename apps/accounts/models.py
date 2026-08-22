from django.conf import settings
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models

from apps.common.models import UUIDPrimaryKeyModel

from .managers import UserManager


def _default_monitor_quota() -> int:
    return settings.MONITORING_DEFAULT_MONITOR_QUOTA


class User(UUIDPrimaryKeyModel, AbstractBaseUser, PermissionsMixin):
    email = models.EmailField(unique=True)
    monitor_quota = models.PositiveIntegerField(default=_default_monitor_quota)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS: list[str] = []

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.email
