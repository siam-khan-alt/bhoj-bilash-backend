from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    AttendanceViewSet,
    ExpenseViewSet,
    HisabSummaryView,
    SalaryViewSet,
    StaffViewSet,
)

router = DefaultRouter(trailing_slash=False)
router.register("staff", StaffViewSet, basename="staff")
router.register("attendance", AttendanceViewSet, basename="attendance")
router.register("expenses", ExpenseViewSet, basename="expenses")
router.register("salary", SalaryViewSet, basename="salary")

urlpatterns = router.urls + [
    path("hisab/summary", HisabSummaryView.as_view(), name="hisab-summary"),
]
