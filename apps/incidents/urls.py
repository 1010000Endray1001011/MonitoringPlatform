from rest_framework.routers import DefaultRouter

from .views import IncidentViewSet

router = DefaultRouter()
router.register("", IncidentViewSet, basename="incident")

app_name = "incidents"
urlpatterns = router.urls
