from rest_framework.permissions import BasePermission


class IsOwner(BasePermission):

    def has_object_permission(self, request, view, obj) -> bool:
        return getattr(obj, "user_id", None) == request.user.id


class IsMonitorOwner(BasePermission):
    """Same idea as IsOwner, for objects that reach their owner through a
    `monitor` FK instead of having a direct `user_id` of their own —
    Incident being the first of those."""

    def has_object_permission(self, request, view, obj) -> bool:
        monitor = getattr(obj, "monitor", None)
        return monitor is not None and monitor.user_id == request.user.id
