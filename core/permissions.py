"""Role guards — cashier is blocked from foods/packages/staff/hisab/settings writes."""

from rest_framework.permissions import BasePermission


class IsAdmin(BasePermission):
    message = "Admin access required."

    def has_permission(self, request, view) -> bool:
        user = request.user
        return bool(user and user.is_authenticated and user.role == "admin")


class IsStaff(BasePermission):
    """Any logged-in staff (admin or cashier)."""

    message = "Staff login required."

    def has_permission(self, request, view) -> bool:
        user = request.user
        return bool(
            user and user.is_authenticated and user.role in ("admin", "cashier")
        )
