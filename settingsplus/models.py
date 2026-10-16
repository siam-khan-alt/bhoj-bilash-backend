"""Settings world — shop config (singleton) + hours + option lists + public reviews.

Conventions (database.md §2.11–2.13):
- 1 copy = 1 dokan: RestaurantConfig has exactly ONE row (id=1 CHECK).
- OpeningHours weekday uses JS getDay() numbering (0 = Sunday), UNIQUE per day.
- OptionList is ONE table for 5 dropdowns. `value` is the stored code — labels
  may change freely, but structural values are locked in code (see views.LOCKED).
- job/category columns in khata/menu are plain strings on purpose, so option
  renames cascade with narrow UPDATEs instead of FK migrations.
"""

from uuid import uuid4

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


def new_option_id() -> str:
    return f"opt_{uuid4().hex[:12]}"


def new_review_id() -> str:
    return f"rev_{uuid4().hex[:12]}"


class RestaurantConfig(models.Model):
    id = models.SmallIntegerField(primary_key=True, default=1)
    slug = models.CharField(max_length=50, default="bhoj-bilash")
    name = models.CharField(max_length=100, default="Bhoj Bilash")
    logo = models.CharField(max_length=500, null=True, blank=True)
    address = models.CharField(max_length=255, null=True, blank=True)
    phone = models.CharField(max_length=20, null=True, blank=True)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=models.Q(id=1), name="config_singleton")
        ]

    def __str__(self) -> str:
        return f"{self.name} [{self.slug}]"


class OpeningHours(models.Model):
    weekday = models.SmallIntegerField(unique=True)  # JS getDay(): 0 = Sunday
    open_time = models.TimeField()
    close_time = models.TimeField()
    closed = models.BooleanField(default=False)

    class Meta:
        ordering = ["weekday"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(weekday__gte=0, weekday__lte=6), name="hours_weekday_0_6"
            ),
            models.CheckConstraint(
                condition=models.Q(close_time__gt=models.F("open_time")),
                name="hours_close_after_open",
            ),
        ]

    def __str__(self) -> str:
        return f"day={self.weekday} {self.open_time}-{self.close_time}{' CLOSED' if self.closed else ''}"


class OptionList(models.Model):
    class ListKey(models.TextChoices):
        FOOD_CATEGORY = "food_category", "Food Category"
        STAFF_JOB = "staff_job", "Staff Job"
        EXPENSE_HEAD = "expense_head", "Expense Head"
        PAYMENT_METHOD = "payment_method", "Payment Method"
        DRINK_SIZE = "drink_size", "Drink Size"

    id = models.TextField(primary_key=True, default=new_option_id)
    list_key = models.CharField(max_length=30, choices=ListKey.choices, db_index=True)
    value = models.CharField(max_length=50)
    label_bn = models.CharField(max_length=100)
    label_en = models.CharField(max_length=100)
    sort_order = models.SmallIntegerField(default=0)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["list_key", "sort_order"]
        constraints = [
            models.UniqueConstraint(fields=["list_key", "value"], name="opt_key_value_unique")
        ]
        indexes = [models.Index(fields=["list_key", "sort_order"])]

    def __str__(self) -> str:
        return f"{self.list_key}:{self.value}"


class Review(models.Model):
    id = models.TextField(primary_key=True, default=new_review_id)
    name = models.CharField(max_length=40)
    rating = models.SmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    text = models.CharField(max_length=300)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["-created_at"])]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(rating__gte=1, rating__lte=5), name="review_rating_1_5"
            )
        ]

    def __str__(self) -> str:
        return f"{self.name} {'*' * self.rating}"
