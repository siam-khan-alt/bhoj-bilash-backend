from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import ConfigView, OptionViewSet, ReviewViewSet

router = DefaultRouter(trailing_slash=False)
router.register("options", OptionViewSet, basename="options")
router.register("reviews", ReviewViewSet, basename="reviews")

urlpatterns = router.urls + [
    path("config", ConfigView.as_view(), name="config"),
]
