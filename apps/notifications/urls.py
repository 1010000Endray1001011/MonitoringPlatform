from rest_framework.routers import DefaultRouter

from .views import NotificationChannelViewSet

router = DefaultRouter()
router.register("", NotificationChannelViewSet, basename="notification-channel")

app_name = "notifications"
urlpatterns = router.urls
