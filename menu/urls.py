from rest_framework.routers import DefaultRouter

from .views import FoodViewSet, PackageViewSet

router = DefaultRouter(trailing_slash=False)
router.register("foods", FoodViewSet, basename="foods")
router.register("packages", PackageViewSet, basename="packages")

urlpatterns = router.urls
