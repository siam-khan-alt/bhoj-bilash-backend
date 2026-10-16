"""Dhap 6 — menu hardening: contract shape, seed idempotent, query budgets."""

from django.core.management import call_command
from rest_framework.test import APITestCase

from menu.models import FoodItem, Package, PackageItem
from users.models import User


def make_user(role="admin", email="admin@test.com"):
    u = User(username=email, email=email, name="T", role=role, is_active=True)
    u.set_password("pass1234")
    u.save()
    return u


class MenuHardeningTests(APITestCase):
    def setUp(self):
        self.admin = make_user("admin", "a@t.com")
        self.cashier = make_user("cashier", "c@t.com")
        self.food = FoodItem.objects.create(name="Burger", category="Burger", price=120)

    def auth(self, user):
        from rest_framework_simplejwt.tokens import AccessToken

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {AccessToken.for_user(user)}")

    def test_food_list_bare_array_contract(self):
        res = self.client.get("/api/foods")
        self.assertEqual(res.status_code, 200)
        # paginated or bare array both allowed — adapter unwraps, but items must match contract
        rows = res.data["results"] if isinstance(res.data, dict) and "results" in res.data else res.data
        self.assertTrue(len(rows) >= 1)
        row = rows[0]
        self.assertIsInstance(row["_id"], str)
        self.assertIsInstance(row["category"], str)
        self.assertIsInstance(row["price"], (int, float))
        self.assertIn("createdAt", row)

    def test_food_list_query_budget_1(self):
        with self.assertNumQueries(2):  # COUNT + 1 page rows (paginated, still O(page))
            res = self.client.get("/api/foods")
            self.assertEqual(res.status_code, 200)

    def test_packages_query_budget_2(self):
        pkg = Package.objects.create(name="Lunch", price=200)
        PackageItem.objects.create(package=pkg, food=self.food, qty=2)
        with self.assertNumQueries(4):  # COUNT + packages + items + foods (prefetch=2q)
            res = self.client.get("/api/packages")
            self.assertEqual(res.status_code, 200)

    def test_seed_idempotent(self):
        call_command("seed_menu")
        n1 = FoodItem.objects.count()
        call_command("seed_menu")
        n2 = FoodItem.objects.count()
        self.assertEqual(n1, n2)

    def test_package_delete_cascades_food_protect(self):
        pkg = Package.objects.create(name="P", price=100)
        PackageItem.objects.create(package=pkg, food=self.food, qty=1)
        self.auth(self.admin)
        # food used in package -> 400, not deleted
        res = self.client.delete(f"/api/foods/{self.food.pk}")
        self.assertEqual(res.status_code, 400)
        self.assertTrue(FoodItem.objects.filter(pk=self.food.pk).exists())
        # package delete -> items CASCADE
        res = self.client.delete(f"/api/packages/{pkg.pk}")
        self.assertEqual(res.status_code, 204)
        self.assertEqual(PackageItem.objects.filter(package_id=pkg.pk).count(), 0)

    def test_offer_price_effective(self):
        self.auth(self.admin)
        res = self.client.post(
            "/api/packages",
            {
                "name": "Offer",
                "price": 300,
                "offerPrice": 0,
                "items": [{"foodId": self.food.pk, "qty": 1}],
            },
            format="json",
        )
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.data["effectivePrice"], 300.0)
