"""Dhap 4 review tests — happy paths + attack paths + query budgets."""

from datetime import date
from decimal import Decimal

from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APITestCase

from khata.models import Attendance, Expense, SalaryPayment, StaffMember
from orders.models import Order
from users.models import User


def make_user(role="admin", email="admin@test.com"):
    user = User(username=email, email=email, name="Test", role=role, is_active=True)
    user.set_password("pass1234")
    user.save()
    return user


class KhataTests(APITestCase):
    def setUp(self):
        self.admin = make_user("admin", "admin@test.com")
        self.cashier = make_user("cashier", "cashier@test.com")
        self.staff = StaffMember.objects.create(
            id="staff_t1", name="Karim", job="baburchi", phone="01700", monthly_salary=30000
        )
        self.today = timezone.localdate()
        self.month = self.today.isoformat()[:7]

    def auth(self, user):
        from rest_framework_simplejwt.tokens import AccessToken

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {AccessToken.for_user(user)}")

    # ---- staff: admin-only, archive default ----

    def test_staff_admin_crud_and_cashier_blocked(self):
        self.auth(self.cashier)
        res = self.client.post(
            "/api/staff", {"name": "X", "monthlySalary": 5000}, format="json"
        )
        self.assertEqual(res.status_code, 403)
        res = self.client.get("/api/staff")
        self.assertEqual(res.status_code, 403)

        self.auth(self.admin)
        res = self.client.post(
            "/api/staff",
            {"name": "Rahim", "job": "helper", "phone": "018", "monthlySalary": 8000},
            format="json",
        )
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.data["monthlySalary"], 8000)
        self.assertTrue(res.data["_id"].startswith("staff_"))
        sid = res.data["_id"]

        res = self.client.post("/api/staff", {"name": "  ", "monthlySalary": 5}, format="json")
        self.assertEqual(res.status_code, 400)
        res = self.client.post("/api/staff", {"name": "Y", "monthlySalary": -5}, format="json")
        self.assertEqual(res.status_code, 400)

        # default delete = archive (still in DB, active=False)
        res = self.client.delete(f"/api/staff/{sid}")
        self.assertEqual(res.status_code, 200)
        self.assertFalse(res.data["active"])
        self.assertTrue(StaffMember.objects.filter(pk=sid).exists())

        # hard delete removes row
        res = self.client.delete(f"/api/staff/{sid}?hard=1")
        self.assertEqual(res.status_code, 204)
        self.assertFalse(StaffMember.objects.filter(pk=sid).exists())

    def test_staff_no_token_401(self):
        res = self.client.get("/api/staff")
        self.assertEqual(res.status_code, 401)

    # ---- attendance: cashier CAN mark, upsert, 404 on times-without-hajira ----

    def test_attendance_upsert_and_times(self):
        self.auth(self.cashier)
        day = self.today.isoformat()
        body = {"staffId": self.staff.pk, "date": day, "status": "present", "inTime": "09:00"}

        res = self.client.post("/api/attendance/mark", body, format="json")
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.data["staffId"], self.staff.pk)
        self.assertEqual(res.data["inTime"], "09:00")

        # same-day re-mark = UPDATE, still 1 row
        res = self.client.post(
            "/api/attendance/mark",
            {"staffId": self.staff.pk, "date": day, "status": "half", "outTime": "18:00"},
            format="json",
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["status"], "half")
        self.assertEqual(Attendance.objects.filter(staff=self.staff, date=self.today).count(), 1)

        # bad inputs
        res = self.client.post(
            "/api/attendance/mark",
            {"staffId": self.staff.pk, "date": day, "status": "sleeping"},
            format="json",
        )
        self.assertEqual(res.status_code, 400)
        res = self.client.post(
            "/api/attendance/mark",
            {"staffId": "staff_nope", "date": day, "status": "present"},
            format="json",
        )
        self.assertEqual(res.status_code, 404)
        res = self.client.post(
            "/api/attendance/mark",
            {"staffId": self.staff.pk, "date": day, "status": "present", "inTime": "25:00"},
            format="json",
        )
        self.assertEqual(res.status_code, 400)

        # times on missing row = 404
        res = self.client.post(
            "/api/attendance/times",
            {"staffId": self.staff.pk, "date": "2000-01-01", "outTime": "18:00"},
            format="json",
        )
        self.assertEqual(res.status_code, 404)

        # times update works on existing row
        res = self.client.post(
            "/api/attendance/times",
            {"staffId": self.staff.pk, "date": day, "outTime": "20:00", "note": "late close"},
            format="json",
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["outTime"], "20:00")

        # month filter
        res = self.client.get(f"/api/attendance?month={self.month}")
        self.assertEqual(res.status_code, 200)

    # ---- expenses: cashier can add, only admin deletes ----

    def test_expense_cashier_add_admin_delete(self):
        self.auth(self.cashier)
        res = self.client.post(
            "/api/expenses",
            {"date": self.today.isoformat(), "category": "bazar", "note": "murgi", "amount": 500, "by": "Karim"},
            format="json",
        )
        self.assertEqual(res.status_code, 201)
        eid = res.data["_id"]

        res = self.client.post("/api/expenses", {"category": "bazar", "amount": -5}, format="json")
        self.assertEqual(res.status_code, 400)

        res = self.client.delete(f"/api/expenses/{eid}")
        self.assertEqual(res.status_code, 403)  # cashier cannot delete

        self.auth(self.admin)
        res = self.client.delete(f"/api/expenses/{eid}")
        self.assertEqual(res.status_code, 204)

    # ---- salary pay (admin) + hisab math ----

    def test_salary_pay_and_hisab_summary_math(self):
        # attendance: 1 present + 1 half in this month -> days = 1.5
        d1 = self.today.replace(day=1)
        Attendance.objects.create(staff=self.staff, date=d1, status="present", in_time="09:00")
        if d1.day < 28:
            from datetime import timedelta

            d2 = d1 + timedelta(days=1)
            if d2.month == d1.month:
                Attendance.objects.create(staff=self.staff, date=d2, status="half")

        present_count = Attendance.objects.filter(staff=self.staff, status="present").count()
        half_count = Attendance.objects.filter(staff=self.staff, status="half").count()
        days = present_count + half_count * 0.5
        expected_payable = round(days * (30000 / 30))  # JS Math.round parity

        self.auth(self.cashier)
        res = self.client.post(
            "/api/salary/pay",
            {"staffId": self.staff.pk, "month": self.month, "amount": 500, "note": "advance"},
            format="json",
        )
        self.assertEqual(res.status_code, 403)  # money-out is admin-only

        self.auth(self.admin)
        res = self.client.post(
            "/api/salary/pay",
            {"staffId": self.staff.pk, "month": self.month, "amount": 500, "note": "advance"},
            format="json",
        )
        self.assertEqual(res.status_code, 201)

        # salary-head expense must NOT inflate expense totals (double-count guard)
        Expense.objects.create(date=self.today, category="salary", note="beton", amount=9999, by="Admin")
        Expense.objects.create(date=self.today, category="bazar", note="sobji", amount=1000, by="Admin")
        Order.objects.create(
            created_by=self.admin, order_status="placed",
            payment_status="paid", payment_method="cash",
            discount=Decimal("0"), total_amount=Decimal("2000"),
        )
        Order.objects.create(
            created_by=self.admin, order_status="cancelled",
            payment_status="paid", payment_method="cash",
            discount=Decimal("0"), total_amount=Decimal("5000"),
        )

        with self.assertNumQueries(9):  # 8 view queries + 1 JWT user lookup
            res = self.client.get(f"/api/hisab/summary?month={self.month}")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["sales"], 2000)  # cancelled excluded
        self.assertEqual(res.data["expenses"], 1000)  # salary head excluded
        self.assertEqual(res.data["salaryPaid"], 500)
        self.assertEqual(res.data["cash"], 500)
        row = next(r for r in res.data["dueByStaff"] if r["staffId"] == self.staff.pk)
        self.assertEqual(row["payable"], expected_payable)
        self.assertEqual(row["paid"], 500)
        self.assertEqual(row["due"], expected_payable - 500)
        self.assertIn("today", res.data)

    def test_hisab_cashier_blocked_and_bad_month(self):
        self.auth(self.cashier)
        res = self.client.get(f"/api/hisab/summary?month={self.month}")
        self.assertEqual(res.status_code, 403)
        self.auth(self.admin)
        res = self.client.get("/api/hisab/summary?month=2026-13")
        self.assertEqual(res.status_code, 400)

    def test_advance_shows_negative_due(self):
        """paid > earned (advance) -> negative due, no crash."""
        Attendance.objects.create(staff=self.staff, date=self.today, status="absent")
        SalaryPayment.objects.create(
            staff=self.staff, month=self.month, amount=5000, note="advance", date=self.today
        )
        self.auth(self.admin)
        res = self.client.get(f"/api/hisab/summary?month={self.month}")
        row = next(r for r in res.data["dueByStaff"] if r["staffId"] == self.staff.pk)
        self.assertEqual(row["payable"], 0)
        self.assertEqual(row["due"], -5000)

    def test_salary_list_month_filter(self):
        SalaryPayment.objects.create(
            staff=self.staff, month="2000-01", amount=100, note="", date=date(2000, 1, 5)
        )
        self.auth(self.admin)
        res = self.client.get("/api/salary?month=2000-01")
        self.assertEqual(res.status_code, 200)
        ids = [r["staffId"] for r in res.data["results"]]
        self.assertIn(self.staff.pk, ids)
        res = self.client.get("/api/salary?month=1999-01")
        self.assertEqual(res.data["results"], [])
        res = self.client.get("/api/salary?month=nope")
        self.assertEqual(res.status_code, 400)
