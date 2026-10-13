"""Idempotent staff seed — re-run safe (update_or_create by fixed id)."""

from django.core.management.base import BaseCommand

from users.models import User

DEMO_USERS = [
    {"id": "u_admin", "name": "Admin", "email": "admin@test.com", "role": "admin", "password": "admin123"},
    {"id": "u_cashier", "name": "Cashier", "email": "cashier@test.com", "role": "cashier", "password": "cashier123"},
]


class Command(BaseCommand):
    help = "Seed demo staff users (admin + cashier). Safe to re-run."

    def handle(self, *args, **options):
        for row in DEMO_USERS:
            user, created = User.objects.update_or_create(
                id=row["id"],
                defaults={
                    "username": row["email"],
                    "name": row["name"],
                    "email": row["email"],
                    "role": row["role"],
                    "is_active": True,
                },
            )
            user.set_password(row["password"])
            user.save(update_fields=["password"])
            self.stdout.write(self.style.SUCCESS(f"{'created' if created else 'updated'} {user}"))
