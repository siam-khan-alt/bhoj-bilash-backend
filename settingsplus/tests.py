"""Dhap 5 review tests — guards + cascade + throttle + open-now parity + budgets."""

from datetime import datetime
from zoneinfo import ZoneInfo

from django.core.cache import cache
from django.utils import timezone
from rest_framework.test import APITestCase

from khata.models import Expense, StaffMember
from menu.models import FoodItem
from settingsplus.models import OpeningHours, OptionList, RestaurantConfig, Review
from settingsplus.views import is_open_now
from users.models import User

DHAKA = ZoneInfo("Asia/Dhaka")


def make_user(role, email):
    user = User(username=email, email=email, name="Test", role=role, is_active=True)
    user.set_password("pass1234")
    user.save()
    return user


def seed_options():
    rows = [
        ("food_category", "Burger"), ("food_category", "Drinks"), ("food_category", "Juice"),
        ("staff_job", "helper"),
        ("expense_head", "bazar"), ("expense_head", "salary"),
    ]
    out = []
    for i, (k, v) in enumerate(rows):
        out.append(
            OptionList.objects.create(
                list_key=k, value=v, label_bn=v, label_en=v, sort_order=i, active=True
            )
        )
    return out


class ConfigTests(APITestCase):
    def setUp(self):
        self.admin = make_user("admin", "a@t.com")
        self.cashier = make_user("cashier", "c@t.com")

    def auth(self, user):
        from rest_framework_simplejwt.tokens import AccessToken

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {AccessToken.for_user(user)}")

    def test_get_seeds_defaults_and_shape(self):
        res = self.client.get("/api/config")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["slug"], "bhoj-bilash")
        self.assertEqual(len(res.data["hours"]), 7)
        self.assertEqual(res.data["hours"][0]["open"], "09:00")
        self.assertEqual(res.data["hours"][5]["close"], "23:00")  # Friday 1h later
        self.assertIn("isOpenNow", res.data)
        # singleton guard
        self.assertEqual(RestaurantConfig.objects.count(), 1)

    def test_get_query_budget(self):
        self.client.get("/api/config")  # first call seeds
        with self.assertNumQueries(2):  # config row + 7 hours
            res = self.client.get("/api/config")
        self.assertEqual(res.status_code, 200)

    def test_patch_admin_only_and_hours_bulk(self):
        day = {"open": "10:00", "close": "21:00"}
        # anon + cashier blocked
        res = self.client.patch("/api/config", {"name": "X"}, format="json")
        self.assertEqual(res.status_code, 401)
        from rest_framework_simplejwt.tokens import AccessToken

        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {AccessToken.for_user(self.cashier)}"
        )
        res = self.client.patch("/api/config", {"name": "X"}, format="json")
        self.assertEqual(res.status_code, 403)

        self.auth(self.admin)
        res = self.client.patch("/api/config", {"name": "  "}, format="json")
        self.assertEqual(res.status_code, 400)
        res = self.client.patch(
            "/api/config",
            {"name": "Notun Dokan", "hours": [day] * 7},
            format="json",
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["name"], "Notun Dokan")
        self.assertEqual(OpeningHours.objects.filter(open_time="10:00").count(), 7)

        res = self.client.patch("/api/config", {"hours": [day] * 6}, format="json")
        self.assertEqual(res.status_code, 400)
        res = self.client.patch(
            "/api/config", {"hours": [{"open": "22:00", "close": "09:00"}] * 7}, format="json"
        )
        self.assertEqual(res.status_code, 400)

    def test_open_now_parity_with_frontend_rule(self):
        """Same rule as frontend isOpenNow: closed day / exact close time edges."""
        from settingsplus.views import ensure_defaults

        _, hours = ensure_defaults()
        # Monday 2026-10-12 noon Dhaka, Sunday 2026-10-11 noon
        monday = datetime(2026, 10, 12, 12, 0, tzinfo=DHAKA)
        sunday = datetime(2026, 10, 11, 12, 0, tzinfo=DHAKA)
        for h in hours:  # only Monday open
            h.closed = h.weekday != 1
            h.open_time = datetime.strptime("09:00", "%H:%M").time()
            h.close_time = datetime.strptime("22:00", "%H:%M").time()
        self.assertTrue(is_open_now(hours, monday))
        self.assertFalse(is_open_now(hours, sunday))  # closed day
        # exact close time = closed (frontend uses cur < close)
        at_close = datetime(2026, 10, 12, 22, 0, tzinfo=DHAKA)
        self.assertFalse(is_open_now(hours, at_close))
        at_open = datetime(2026, 10, 12, 9, 0, tzinfo=DHAKA)
        self.assertTrue(is_open_now(hours, at_open))

    def test_config_get_reflects_closed_today(self):
        self.client.get("/api/config")  # seed
        today = timezone.localtime().isoweekday() % 7
        row = OpeningHours.objects.get(weekday=today)
        row.closed = True
        row.save(update_fields=["closed"])
        res = self.client.get("/api/config")
        self.assertFalse(res.data["isOpenNow"])


class OptionTests(APITestCase):
    def setUp(self):
        self.admin = make_user("admin", "a2@t.com")
        self.cashier = make_user("cashier", "c2@t.com")
        seed_options()

    def auth(self, user):
        from rest_framework_simplejwt.tokens import AccessToken

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {AccessToken.for_user(user)}")

    def test_list_requires_key_sort_and_active(self):
        res = self.client.get("/api/options")
        self.assertEqual(res.status_code, 400)
        res = self.client.get("/api/options?key=nope")
        self.assertEqual(res.status_code, 400)
        with self.assertNumQueries(1):
            res = self.client.get("/api/options?key=food_category")
        self.assertEqual(res.status_code, 200)
        self.assertEqual([r["value"] for r in res.data], ["Burger", "Drinks", "Juice"])
        self.assertEqual(res.data[0]["key"], "food_category")
        self.assertIn("sort", res.data[0])

    def test_write_admin_only(self):
        self.client.credentials()  # anon
        res = self.client.post(
            "/api/options", {"key": "food_category", "value": "Nasta"}, format="json"
        )
        self.assertEqual(res.status_code, 401)
        self.auth(self.cashier)
        res = self.client.post(
            "/api/options", {"key": "food_category", "value": "Nasta"}, format="json"
        )
        self.assertEqual(res.status_code, 403)

    def test_add_and_duplicate_case_insensitive(self):
        self.auth(self.admin)
        res = self.client.post(
            "/api/options",
            {"key": "food_category", "value": "Nasta", "label_bn": "নাস্তা"},
            format="json",
        )
        self.assertEqual(res.status_code, 201)
        self.assertTrue(res.data["_id"].startswith("opt_"))
        res = self.client.post(
            "/api/options", {"key": "food_category", "value": "nasta"}, format="json"
        )
        self.assertEqual(res.status_code, 400)
        res = self.client.post("/api/options", {"key": "food_category", "value": " "}, format="json")
        self.assertEqual(res.status_code, 400)

    def test_locked_rename_delete_400(self):
        self.auth(self.admin)
        salary = OptionList.objects.get(list_key="expense_head", value="salary")
        res = self.client.patch(f"/api/options/{salary.pk}", {"value": "beton"}, format="json")
        self.assertEqual(res.status_code, 400)
        res = self.client.delete(f"/api/options/{salary.pk}")
        self.assertEqual(res.status_code, 400)
        drinks = OptionList.objects.get(list_key="food_category", value="Drinks")
        res = self.client.patch(f"/api/options/{drinks.pk}", {"value": "Soda"}, format="json")
        self.assertEqual(res.status_code, 400)
        # label change on locked value is FINE
        res = self.client.patch(
            f"/api/options/{drinks.pk}", {"label_bn": "পানীয়-x"}, format="json"
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(OptionList.objects.get(pk=drinks.pk).value, "Drinks")

    def test_rename_cascade_all_three_tables(self):
        burger = FoodItem.objects.create(name="B", category="Burger", price=100)
        staff = StaffMember.objects.create(name="K", job="helper", monthly_salary=5000)
        exp = Expense.objects.create(date="2026-10-01", category="bazar", note="x", amount=50, by="A")
        self.auth(self.admin)
        burger_pk = OptionList.objects.get(value="Burger").pk
        with self.assertNumQueries(7):  # auth + fetch + dup + save + cascade + atomic framing x2
            res = self.client.patch(
                f"/api/options/{burger_pk}",
                {"value": "Bhaat"},
                format="json",
            )
        self.assertEqual(res.status_code, 200)
        burger.refresh_from_db()
        self.assertEqual(burger.category, "Bhaat")

        res = self.client.patch(
            f"/api/options/{OptionList.objects.get(value='helper').pk}",
            {"value": "assistant"},
            format="json",
        )
        self.assertEqual(res.status_code, 200)
        staff.refresh_from_db()
        self.assertEqual(staff.job, "assistant")

        res = self.client.patch(
            f"/api/options/{OptionList.objects.get(value='bazar').pk}",
            {"value": "kacha-bazar"},
            format="json",
        )
        self.assertEqual(res.status_code, 200)
        exp.refresh_from_db()
        self.assertEqual(exp.category, "kacha-bazar")

    def test_delete_referenced_blocked_with_usage(self):
        FoodItem.objects.create(name="B", category="Burger", price=100)
        self.auth(self.admin)
        row = OptionList.objects.get(value="Burger")
        res = self.client.delete(f"/api/options/{row.pk}")
        self.assertEqual(res.status_code, 400)
        self.assertIn("food", res.data["message"])
        # unreferenced + unlocked value deletes clean
        res = self.client.post(
            "/api/options", {"key": "food_category", "value": "Nasta"}, format="json"
        )
        self.assertEqual(res.status_code, 201)
        res = self.client.delete(f"/api/options/{res.data['_id']}")
        self.assertEqual(res.status_code, 204)


class ReviewTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.admin = make_user("admin", "a3@t.com")

    def test_list_newest_first_and_stats(self):
        Review.objects.create(name="A", rating=5, text="valo")
        Review.objects.create(name="B", rating=3, text="mota-muti")
        res = self.client.get("/api/reviews")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["results"][0]["name"], "B")  # newest first
        with self.assertNumQueries(1):
            res = self.client.get("/api/reviews/stats")
        self.assertEqual(res.data, {"average": 4.0, "count": 2})

    def test_post_validation(self):
        res = self.client.post(
            "/api/reviews", {"name": "K", "rating": 5, "text": "darun"}, format="json"
        )
        self.assertEqual(res.status_code, 201)
        self.assertTrue(res.data["_id"].startswith("rev_"))
        cache.clear()  # throttle counts every POST — reset so validation is tested pure
        for bad in [
            {"name": "", "rating": 5, "text": "x"},
            {"name": "K", "rating": 0, "text": "x"},
            {"name": "K", "rating": 6, "text": "x"},
            {"name": "K", "rating": 5, "text": " "},
            {"name": "K", "rating": 5, "text": "x" * 301},
        ]:
            res = self.client.post("/api/reviews", bad, format="json")
            self.assertEqual(res.status_code, 400, bad)

    def test_spam_throttle_429_on_6th(self):
        for i in range(5):
            res = self.client.post(
                "/api/reviews",
                {"name": f"U{i}", "rating": 5, "text": f"review {i}"},
                format="json",
            )
            self.assertEqual(res.status_code, 201, i)
        res = self.client.post(
            "/api/reviews", {"name": "U5", "rating": 5, "text": "spam"}, format="json"
        )
        self.assertEqual(res.status_code, 429)
        self.assertIn("message", res.data)
