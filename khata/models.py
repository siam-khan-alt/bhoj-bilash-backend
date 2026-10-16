"""Khata models — hajira-beton-khoroch. TEXT PKs (staff_/att_/exp_/sal_) so frontend `_id` needs zero mapping.

Conventions (database.md §2.7–2.10):
- `job` / expense `category` are PLAIN STRINGS — no choices constraint, because
  `/admin/settings` option lists can add custom values at runtime.
- Expense `by` stores staff NAME snapshot (frontend sends name string), not FK.
- Salary earned is DERIVED (attendance x per-day) — this app stores only what was
  actually handed over (SalaryPayment). Due = earned - paid (negative = advance).
"""

from uuid import uuid4

from django.core.validators import MinValueValidator
from django.db import models


def new_staff_id() -> str:
    return f"staff_{uuid4().hex[:12]}"


def new_attendance_id() -> str:
    return f"att_{uuid4().hex[:12]}"


def new_expense_id() -> str:
    return f"exp_{uuid4().hex[:12]}"


def new_salary_id() -> str:
    return f"sal_{uuid4().hex[:12]}"


class StaffMember(models.Model):
    """Khata people — baburchi/helper/cashier. NOT login users (see users.User)."""

    id = models.TextField(primary_key=True, default=new_staff_id)
    name = models.CharField(max_length=100)
    # plain string, default helper — option_lists may add more jobs later
    job = models.CharField(max_length=30, default="helper")
    phone = models.CharField(max_length=20, default="", blank=True)
    monthly_salary = models.DecimalField(
        max_digits=10, decimal_places=2, validators=[MinValueValidator(0.01)]
    )
    active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
        indexes = [models.Index(fields=["active"])]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(monthly_salary__gt=0), name="staff_salary_gt_0"
            )
        ]

    def __str__(self) -> str:
        return f"{self.name} [{self.job}] ৳{self.monthly_salary}"


class Attendance(models.Model):
    """One row per staff per day. Entry in morning, exit at night (update same row)."""

    class Status(models.TextChoices):
        PRESENT = "present", "Present"
        ABSENT = "absent", "Absent"
        HALF = "half", "Half"
        LEAVE = "leave", "Leave"

    id = models.TextField(primary_key=True, default=new_attendance_id)
    staff = models.ForeignKey(
        StaffMember, related_name="attendance", on_delete=models.CASCADE
    )
    date = models.DateField()
    status = models.CharField(max_length=10, choices=Status.choices)
    in_time = models.CharField(max_length=5, default="", blank=True)
    out_time = models.CharField(max_length=5, default="", blank=True)
    note = models.TextField(default="", blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["date", "created_at"]
        constraints = [
            # upsert key — re-marking same day updates the row, never duplicates
            models.UniqueConstraint(fields=["staff", "date"], name="att_staff_date_unique")
        ]
        indexes = [models.Index(fields=["date"])]

    def __str__(self) -> str:
        return f"{self.staff_id} {self.date} [{self.status}]"


class Expense(models.Model):
    """Khoroch ledger. `by` = staff name snapshot, not FK (frontend sends name)."""

    id = models.TextField(primary_key=True, default=new_expense_id)
    date = models.DateField(db_index=True)
    # plain string (bazar/salary/rent/utility/other + custom from option lists)
    category = models.CharField(max_length=30)
    note = models.CharField(max_length=255)
    amount = models.DecimalField(
        max_digits=10, decimal_places=2, validators=[MinValueValidator(0.01)]
    )
    by = models.CharField(max_length=100, default="", blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date", "-created_at"]
        indexes = [models.Index(fields=["date"])]

    def __str__(self) -> str:
        return f"{self.date} {self.category}: ৳{self.amount} ({self.note})"


class SalaryPayment(models.Model):
    """Beton/advance given. `month` is the LEDGER month (YYYY-MM), may differ from pay `date`."""

    id = models.TextField(primary_key=True, default=new_salary_id)
    staff = models.ForeignKey(
        StaffMember, related_name="salary_payments", on_delete=models.CASCADE
    )
    month = models.CharField(max_length=7)
    amount = models.DecimalField(
        max_digits=10, decimal_places=2, validators=[MinValueValidator(0.01)]
    )
    note = models.CharField(max_length=255, default="", blank=True)
    date = models.DateField(db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date", "-created_at"]
        indexes = [models.Index(fields=["staff", "month"])]

    def __str__(self) -> str:
        return f"{self.staff_id} {self.month}: ৳{self.amount}"
