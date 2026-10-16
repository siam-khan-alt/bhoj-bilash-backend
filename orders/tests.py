"""Dhap 6 — orders hardening: money attacks, atomicity, query budgets."""

from decimal import Decimal

from rest_framework.test import APITestCase

from menu.models import FoodItem
from orders.models import Order
from users.models import User


def make_user(role="admin", email="admin@test.com"):
    u = User(username=email, email=email, name="T", role=role, is_active=True)
    u.set_password("pass1234")
    u.save()
    return u


class OrderHardeningTests(APITestCase):
    def setUp(self):
        self.admin = make_user("admin", "a@t.com")
        self.cashier = make_user("cashier", "c@t.com")
        self.burger = FoodItem.objects.create(name="Burger", category="Burger", price=120)
        self.juice = FoodItem.objects.create(name="Juice", category="Juice", price=60)

    def auth(self, user):
        from rest_framework_simplejwt.tokens import AccessToken

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {AccessToken.for_user(user)}")

    def _create(self, items, **extra):
        body = {"items": items, "customerPhone": "01700", **extra}
        return self.client.post("/api/orders", body, format="json")

    def test_wrong_price_attack_server_wins(self):
        """Client kom dam pathaleo server DB dam-e total korbe."""
        self.auth(self.cashier)
        res = self._create(
            [
                {"foodItemId": self.burger.pk, "quantity": 2, "price": 1},
                {"foodItemId": self.juice.pk, "quantity": 1, "price": 1},
            ]
        )
        self.assertEqual(res.status_code, 201)
        order = res.data["order"]
        self.assertEqual(order["totalAmount"], 300.0)  # 120*2 + 60, NOT 3
        self.assertEqual(order["items"][0]["price"], 120.0)

    def test_discount_clamp_and_negative_reject(self):
        self.auth(self.cashier)
        res = self._create([{"foodItemId": self.burger.pk, "quantity": 1}], discount=99999)
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.data["order"]["totalAmount"], 0.0)
        res = self._create([{"foodItemId": self.burger.pk, "quantity": -2}])
        self.assertEqual(res.status_code, 400)

    def test_package_pseudo_line_single(self):
        self.auth(self.cashier)
        res = self._create(
            [{"foodItemId": "pkgline_1", "quantity": 1, "label": "Lunch Package", "price": 250}]
        )
        self.assertEqual(res.status_code, 201)
        item = res.data["order"]["items"][0]
        self.assertEqual(item["foodItem"]["category"], "Package")
        self.assertEqual(item["price"], 250.0)

    def test_atomicity_one_bad_item_zero_order(self):
        self.auth(self.cashier)
        before = Order.objects.count()
        res = self._create(
            [
                {"foodItemId": self.burger.pk, "quantity": 1},
                {"foodItemId": "food_nope", "quantity": 1},
            ]
        )
        self.assertEqual(res.status_code, 400)
        self.assertEqual(Order.objects.count(), before)

    def test_create_query_budget_and_list_page(self):
        self.auth(self.cashier)
        with self.assertNumQueries(9):  # JWT + bulk food + savepoint/insert/release + refetch(3)
            res = self._create([{"foodItemId": self.burger.pk, "quantity": 1}])
            self.assertEqual(res.status_code, 201)
        with self.assertNumQueries(5):  # JWT + COUNT + rows + items + foods
            res = self.client.get("/api/orders")
            self.assertEqual(res.status_code, 200)

    def test_status_admin_only_cashier_403(self):
        self.auth(self.cashier)
        res = self._create([{"foodItemId": self.burger.pk, "quantity": 1}])
        oid = res.data["order"]["_id"]
        res = self.client.patch(f"/api/orders/{oid}/status", {"orderStatus": "preparing"}, format="json")
        self.assertEqual(res.status_code, 403)
        self.auth(self.admin)
        res = self.client.patch(f"/api/orders/{oid}/status", {"orderStatus": "preparing"}, format="json")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["orderStatus"], "preparing")
        res = self.client.patch(f"/api/orders/{oid}/status", {"orderStatus": "flying"}, format="json")
        self.assertEqual(res.status_code, 400)

    def test_by_phone_groups_not_by_id(self):
        self.auth(self.cashier)
        self._create([{"foodItemId": self.burger.pk, "quantity": 1}], customerPhone="01811")
        self._create([{"foodItemId": self.juice.pk, "quantity": 2}], customerPhone="01811")
        res = self.client.get("/api/orders/by-phone?phone=01811")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["totalOrders"], 2)
        self.assertEqual(res.data["totalSpent"], 240.0)
