"""Dhap 6 — auth hardening: login shape, 401/403 matrix, error shape."""

from rest_framework.test import APITestCase

from users.models import User


def make_user(role="admin", email="admin@test.com", name="Test"):
    u = User(username=email, email=email, name=name, role=role, is_active=True)
    u.set_password("pass1234")
    u.save()
    return u


class AuthHardeningTests(APITestCase):
    def setUp(self):
        self.admin = make_user("admin", "admin@test.com", "Malik")
        self.cashier = make_user("cashier", "cashier@test.com", "Cashier")

    def _login(self, email, password):
        return self.client.post(
            "/api/auth/login", {"email": email, "password": password}, format="json"
        )

    def _token(self, user):
        from rest_framework_simplejwt.tokens import AccessToken

        return str(AccessToken.for_user(user))

    # ---- happy path ----
    def test_login_shape_user_token(self):
        res = self._login("admin@test.com", "pass1234")
        self.assertEqual(res.status_code, 200)
        self.assertIn("token", res.data)
        self.assertNotIn("access", res.data)
        self.assertNotIn("refresh", res.data)
        user = res.data["user"]
        for key in ("_id", "name", "email", "role", "createdAt"):
            self.assertIn(key, user)
        self.assertEqual(user["role"], "admin")
        self.assertNotIn("password", str(res.data))

    def test_me_restores_session(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self._token(self.admin)}")
        res = self.client.get("/api/auth/me")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["email"], "admin@test.com")

    # ---- attack paths ----
    def test_wrong_password_401_message_shape(self):
        res = self._login("admin@test.com", "wrong-pass")
        self.assertEqual(res.status_code, 401)
        self.assertIn("message", res.data)

    def test_unknown_email_401(self):
        res = self._login("nope@test.com", "pass1234")
        self.assertEqual(res.status_code, 401)
        self.assertIn("message", res.data)

    def test_no_token_admin_api_401(self):
        for url in ("/api/staff", "/api/hisab/summary?month=2026-10", "/api/foods"):
            res = self.client.post(
                "/api/foods", {"name": "X", "category": "Burger", "price": 10}, format="json"
            ) if url == "/api/foods" else self.client.get(url)
            self.assertIn(res.status_code, (401, 403), url)
        # food list is public — must stay 200 without token
        res = self.client.get("/api/foods")
        self.assertEqual(res.status_code, 200)

    def test_cashier_blocked_from_admin_writes_403(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self._token(self.cashier)}")
        res = self.client.post(
            "/api/foods", {"name": "X", "category": "Burger", "price": 10}, format="json"
        )
        self.assertEqual(res.status_code, 403)
        # cashier CAN do POS work
        res = self.client.get("/api/attendance?month=2026-10")
        self.assertIn(res.status_code, (200, 400))

    def test_401_403_matrix_documented(self):
        """Endpoint x no-token/cashier/admin — Dhap 6 review checklist proof."""
        cases = [
            ("post", "/api/foods", 401, 403, 201),
            ("get", "/api/staff", 401, 403, 200),
            ("get", "/api/hisab/summary?month=2026-10", 401, 403, 200),
        ]
        for method, url, expect_anon, expect_cashier, expect_admin in cases:
            body = {"name": "M", "category": "Burger", "price": 10, "monthlySalary": 5000}
            # anon
            self.client.credentials()
            res = getattr(self.client, method)(url, body, format="json")
            self.assertEqual(res.status_code, expect_anon, f"anon {method} {url}")
            # cashier
            self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self._token(self.cashier)}")
            res = getattr(self.client, method)(url, body, format="json")
            self.assertEqual(res.status_code, expect_cashier, f"cashier {method} {url}")
            # admin
            self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self._token(self.admin)}")
            res = getattr(self.client, method)(url, body, format="json")
            self.assertIn(res.status_code, (expect_admin, 200, 201), f"admin {method} {url}")
