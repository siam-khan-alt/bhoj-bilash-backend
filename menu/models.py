"""Menu models — TEXT PKs (food_/pkg_) so frontend `_id` needs zero mapping."""

from uuid import uuid4

from django.core.validators import MinValueValidator
from django.db import models


def new_food_id() -> str:
    return f"food_{uuid4().hex[:12]}"


def new_package_id() -> str:
    return f"pkg_{uuid4().hex[:12]}"


class FoodItem(models.Model):
    id = models.TextField(primary_key=True, default=new_food_id)
    name = models.CharField(max_length=150)
    # plain string — deliberately NO categories table (database.md §2.2)
    category = models.CharField(max_length=50, db_index=True)
    price = models.DecimalField(
        max_digits=10, decimal_places=2, validators=[MinValueValidator(0)]
    )
    image = models.CharField(max_length=500, blank=True, default="")
    available = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["category"]),
            models.Index(fields=["available"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(price__gte=0), name="food_price_gte_0"
            )
        ]

    def __str__(self) -> str:
        return f"{self.name} [{self.category}] ৳{self.price}"


class Package(models.Model):
    id = models.TextField(primary_key=True, default=new_package_id)
    name = models.CharField(max_length=150)
    price = models.DecimalField(
        max_digits=10, decimal_places=2, validators=[MinValueValidator(0)]
    )
    offer_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
    )
    offer_note = models.CharField(max_length=100, null=True, blank=True)
    image = models.CharField(max_length=500, blank=True, default="")
    active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["active"])]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(price__gte=0), name="pkg_price_gte_0"
            ),
            models.CheckConstraint(
                condition=models.Q(offer_price__isnull=True)
                | models.Q(offer_price__gte=0),
                name="pkg_offer_gte_0",
            ),
        ]

    @property
    def effective_price(self):
        if self.offer_price is not None and self.offer_price > 0:
            return self.offer_price
        return self.price

    def __str__(self) -> str:
        return f"{self.name} ৳{self.effective_price}"


class PackageItem(models.Model):
    package = models.ForeignKey(
        Package, related_name="items", on_delete=models.CASCADE
    )
    # PROTECT — menu item in a bundle can't be deleted (review checklist)
    food = models.ForeignKey(
        FoodItem, related_name="package_lines", on_delete=models.PROTECT
    )
    qty = models.PositiveSmallIntegerField()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["package", "food"], name="pkg_food_unique"
            )
        ]

    def __str__(self) -> str:
        return f"{self.package_id} x {self.food_id} ({self.qty})"
