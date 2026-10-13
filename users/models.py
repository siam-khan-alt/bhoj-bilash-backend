from uuid import uuid4

from django.contrib.auth.models import AbstractUser
from django.db import models


def _new_user_id() -> str:
    # Module-level (not a closure) so migration files can serialize it.
    return f"u_{uuid4().hex[:12]}"


class User(AbstractUser):
    """Staff login ONLY (no customers) — role: admin (everything) | cashier (POS/orders/khata)."""

    class Role(models.TextChoices):
        ADMIN = "admin", "Admin"
        CASHIER = "cashier", "Cashier"

    id = models.TextField(primary_key=True, default=_new_user_id)
    first_name = None  # type: ignore[assignment]  # single `name` field instead
    last_name = None  # type: ignore[assignment]

    name = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    role = models.CharField(max_length=10, choices=Role.choices, default=Role.CASHIER)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username", "name"]

    def save(self, *args, **kwargs):
        if not self.username:
            self.username = self.email
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.name} <{self.email}> [{self.role}]"
