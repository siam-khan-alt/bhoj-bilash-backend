from rest_framework.routers import DefaultRouter

from .views import OrderViewSet

router = DefaultRouter(trailing_slash=False)
router.register("orders", OrderViewSet, basename="orders")

urlpatterns = router.urls
