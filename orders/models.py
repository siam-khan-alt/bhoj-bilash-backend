"""Orders — walk-in bills. Server recomputes ALL money, never trusts client."""

from decimal import Decimal
from uuid import uuid4

from django.core.validators import MinValueValidator
from django.db import models


def new_order_id() -> str:
    return f"order_{uuid4().hex[:12]}"


class Order(models.Model):
    class OrderType(models.TextChoices):
        DINE_IN = "dine_in", "Dine In"
        PARCEL = "parcel", "Parcel"
        BOTH = "both", "Both"

    class OrderStatus(models.TextChoices):
        PLACED = "placed", "Placed"
        PREPARING = "preparing", "Preparing"
        DELIVERED = "delivered", "Delivered"
        CANCELLED = "cancelled", "Cancelled"

    class PaymentStatus(models.TextChoices):
        PENDING = "pending", "Pending"
        PAID = "paid", "Paid"
        FAILED = "failed", "Failed"

    class PaymentMethod(models.TextChoices):
        CASH = "cash", "Cash"
        CARD = "card", "Card"

    id = models.TextField(primary_key=True, default=new_order_id)
    created_by = models.ForeignKey(
        "users.User", related_name="orders", on_delete=models.PROTECT
    )
    # only real customer data point — POS types a phone (database.md §2.5)
    customer_phone = models.CharField(max_length=20, null=True, blank=True)
    order_type = models.CharField(
        max_length=10, choices=OrderType.choices, default=OrderType.DINE_IN
    )
    order_status = models.CharField(
        max_length=20, choices=OrderStatus.choices, default=OrderStatus.PLACED
    )
    payment_status = models.CharField(
        max_length=20, choices=PaymentStatus.choices, default=PaymentStatus.PAID
    )
    payment_method = models.CharField(
        max_length=10, choices=PaymentMethod.choices, default=PaymentMethod.CASH
    )
    discount = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal("0"),
        validators=[MinValueValidator(0)],
    )
    total_amount = models.DecimalField(
        max_digits=10, decimal_places=2, validators=[MinValueValidator(0)]
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["created_by"]),
            models.Index(fields=["-created_at"]),
            models.Index(fields=["order_status"]),
            models.Index(fields=["customer_phone"]),
        ]

    def __str__(self) -> str:
        return f"{self.id} ৳{self.total_amount} [{self.order_status}]"


class OrderItem(models.Model):
    order = models.ForeignKey(
        Order, related_name="items", on_delete=models.CASCADE
    )
    # NULL = package pseudo-line (label + price snapshot, no real food row)
    food_item = models.ForeignKey(
        "menu.FoodItem", related_name="order_lines",
        null=True, blank=True, on_delete=models.SET_NULL,
    )
    item_name = models.CharField(max_length=150)
    quantity = models.PositiveSmallIntegerField()
    price = models.DecimalField(
        max_digits=10, decimal_places=2, validators=[MinValueValidator(0)]
    )

    class Meta:
        indexes = [
            models.Index(fields=["order"]),
            models.Index(fields=["food_item"]),
        ]

    def __str__(self) -> str:
        return f"{self.order_id} {self.item_name} x{self.quantity}"
