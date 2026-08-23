from rest_framework.routers import DefaultRouter

from .views import MonitorViewSet

router = DefaultRouter()
router.register("", MonitorViewSet, basename="monitor")

app_name = "monitors"
urlpatterns = router.urls
