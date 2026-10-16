"""Idempotent khata seed — mirrors frontend mockStaff + mockExpenses. Re-run safe."""

from django.core.management.base import BaseCommand
from django.utils import timezone

from khata.models import Expense, StaffMember

STAFF = [
    {"id": "staff_001", "name": "Karim Baburchi", "job": "baburchi", "phone": "01700-111111", "monthly_salary": 15000},
    {"id": "staff_002", "name": "Rahim Helper", "job": "helper", "phone": "01700-222222", "monthly_salary": 8000},
]


class Command(BaseCommand):
    help = "Seed khata staff (attendance/expenses are day-data, not seeded). Safe to re-run."

    def handle(self, *args, **options):
        for row in STAFF:
            StaffMember.objects.update_or_create(
                id=row["id"],
                defaults={
                    "name": row["name"],
                    "job": row["job"],
                    "phone": row["phone"],
                    "monthly_salary": row["monthly_salary"],
                    "active": True,
                },
            )
        today = timezone.localdate().isoformat()
        Expense.objects.update_or_create(
            id="exp_001",
            defaults={
                "date": today,
                "category": "bazar",
                "note": "Murgi 5kg + sobji",
                "amount": 1850,
                "by": "Admin",
            },
        )
        Expense.objects.update_or_create(
            id="exp_002",
            defaults={
                "date": today,
                "category": "utility",
                "note": "Gas bill",
                "amount": 1200,
                "by": "Admin",
            },
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"seeded {StaffMember.objects.count()} staff, {Expense.objects.count()} expenses"
            )
        )
