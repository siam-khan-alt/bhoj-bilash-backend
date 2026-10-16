"""Khata views — hajira-beton-khoroch + hisab summary. All math in DB, never Python loops.

Query budgets (fixed, row-count independent):
- staff list ............ 1 query
- attendance ?month= .... 1 query (staff_id,date index range scan)
- expenses list ......... 1 query (date index, paginated)
- salary ?month= ........ 1 query
- mark (upsert) ......... 1 SELECT + 1 INSERT-or-UPDATE (UNIQUE hit, O(log n))
- hisab/summary ......... 8 fixed queries (month sales/exp/att/pay/staff + today sales/exp/sal)

Permission model (senior call — matches core.permissions docstring):
- staff CRUD ............ IsAdmin (full). Cashier gets 403 on write AND list.
- hisab/summary ......... IsAdmin (money summary is malik-only; UI already redirects cashier).
- attendance ............ IsStaff (cashier marks hajira at the counter).
- expenses .............. IsStaff, EXCEPT destroy = IsAdmin (entry allowed, deletion malik-only).
- salary list ........... IsStaff, pay = IsAdmin (money-out is malik-only).

Frontend mapping (adapter swaps inside lib/api/* only, signatures stay same):
- getStaff/addStaff/updateStaff/deleteStaff .. StaffViewSet (DELETE default archives, ?hard=1 hard-deletes)
- getAttendanceByDate/Month .................. GET /api/attendance?date=|month=
- markAttendance ............................. POST /api/attendance/mark (upsert)
- updateAttendanceTimes ...................... POST|PATCH /api/attendance/times (404 if no hajira yet)
- get/add/update/deleteExpense ............... ExpenseViewSet
- getSalaryPayments(month) ................... GET /api/salary?month=
- paySalary .................................. POST /api/salary/pay
- hisab page (4 mock calls today) ............ GET /api/hisab/summary?month=&date= (1 call)
"""

import calendar
import re
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP

from django.db.models import Case, Count, Q, Sum, When
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from core.permissions import IsAdmin, IsStaff
from orders.models import Order

from .models import Attendance, Expense, SalaryPayment, StaffMember
from .serializers import (
    AttendanceSerializer,
    ExpenseSerializer,
    SalaryPaymentSerializer,
    StaffSerializer,
)

MONTH_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")
TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


def _month_range(month: str) -> tuple[date, date]:
    """YYYY-MM -> (first_day_inclusive, next_first_exclusive). No string LIKE — date range."""
    year, mon = int(month[:4]), int(month[5:7])
    first = date(year, mon, 1)
    last_day = calendar.monthrange(year, mon)[1]
    if mon == 12:
        nxt = date(year + 1, 1, 1)
    else:
        nxt = date(year, mon + 1, 1)
    void = last_day  # keep linter honest about month length (unused)
    _ = void
    return first, nxt


def _parse_date(value) -> date | None:
    try:
        return date.fromisoformat(str(value))
    except (ValueError, TypeError):
        return None


def _parse_month(value) -> str | None:
    value = str(value or "").strip()
    return value if MONTH_RE.match(value) else None


def _today() -> date:
    return timezone.localdate()


def _valid_time(value) -> bool:
    return bool(TIME_RE.match(str(value or "")))


def _earned(monthly_salary, days: float) -> int:
    """Match frontend monthPayable: Math.round(days * salary/30). HALF_UP (JS Math.round, not banker's)."""
    per_day = Decimal(str(monthly_salary)) / Decimal("30")
    return int((per_day * Decimal(str(days))).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


# ---------------------------------------------------------------- staff ---


class StaffViewSet(viewsets.ModelViewSet):
    """GET /api/staff (admin) / POST / PATCH / DELETE (admin, default = archive)."""

    queryset = StaffMember.objects.all().order_by("created_at")
    serializer_class = StaffSerializer
    permission_classes = [IsAdmin]
    http_method_names = ["get", "post", "patch", "put", "delete", "head", "options"]

    def get_queryset(self):
        qs = super().get_queryset()
        active = self.request.query_params.get("active")
        if active in ("1", "true", "True"):
            qs = qs.filter(active=True)
        elif active in ("0", "false", "False"):
            qs = qs.filter(active=False)
        return qs

    def create(self, request, *args, **kwargs):
        data = request.data
        name = str(data.get("name", "")).strip()
        if not name:
            return Response({"message": "Staff name required."}, status=400)
        try:
            salary = Decimal(str(data.get("monthlySalary", data.get("monthly_salary", 0))))
        except Exception:
            return Response({"message": "Valid monthly salary required."}, status=400)
        if salary <= 0:
            return Response({"message": "Salary must be > 0."}, status=400)
        staff = StaffMember.objects.create(
            name=name[:100],
            job=str(data.get("job", "") or "helper").strip()[:30] or "helper",
            phone=str(data.get("phone", "") or "").strip()[:20],
            monthly_salary=salary,
            active=True,
        )
        return Response(StaffSerializer(staff).data, status=201)

    def partial_update(self, request, *args, **kwargs):
        return self._patch(request, **kwargs)

    def update(self, request, *args, **kwargs):
        return self._patch(request, **kwargs)

    def _patch(self, request, **kwargs):
        staff = get_object_or_404(StaffMember, pk=kwargs["pk"])
        data = request.data
        if "name" in data:
            name = str(data["name"] or "").strip()
            if not name:
                return Response({"message": "Staff name required."}, status=400)
            staff.name = name[:100]
        if "job" in data:
            staff.job = str(data["job"] or "").strip()[:30] or "helper"
        if "phone" in data:
            staff.phone = str(data["phone"] or "").strip()[:20]
        if "monthlySalary" in data or "monthly_salary" in data:
            raw = data.get("monthlySalary", data.get("monthly_salary"))
            try:
                salary = Decimal(str(raw))
            except Exception:
                return Response({"message": "Valid monthly salary required."}, status=400)
            if salary <= 0:
                return Response({"message": "Salary must be > 0."}, status=400)
            staff.monthly_salary = salary
        if "active" in data:
            staff.active = bool(data["active"])
        staff.save()
        return Response(StaffSerializer(staff).data)

    def destroy(self, request, *args, **kwargs):
        """Default = archive (active=False, 200). ?hard=1 = hard delete (204)."""
        staff = get_object_or_404(StaffMember, pk=kwargs["pk"])
        hard = request.query_params.get("hard")
        if hard in ("1", "true", "True"):
            staff.delete()  # cascades attendance + salary rows
            return Response(status=status.HTTP_204_NO_CONTENT)
        staff.active = False
        staff.save(update_fields=["active"])
        return Response(StaffSerializer(staff).data)


# ----------------------------------------------------------- attendance ---


class AttendanceViewSet(viewsets.GenericViewSet):
    """GET list (?date=|?month=) + POST /mark (upsert) + POST|PATCH /times."""

    queryset = Attendance.objects.all().select_related("staff").order_by("date", "created_at")
    serializer_class = AttendanceSerializer
    permission_classes = [IsStaff]

    def list(self, request, *args, **kwargs):
        qs = self.get_queryset()
        day = request.query_params.get("date")
        month = request.query_params.get("month")
        staff_id = request.query_params.get("staffId", request.query_params.get("staff_id"))
        if staff_id:
            qs = qs.filter(staff_id=staff_id)
        if day:
            parsed = _parse_date(day)
            if parsed is None:
                return Response({"message": "Invalid date (YYYY-MM-DD)."}, status=400)
            qs = qs.filter(date=parsed)
        elif month:
            if not _parse_month(month):
                return Response({"message": "Invalid month (YYYY-MM)."}, status=400)
            first, nxt = _month_range(month)
            qs = qs.filter(date__gte=first, date__lt=nxt)
        page = self.paginate_queryset(qs)
        if page is not None:
            return self.get_paginated_response(AttendanceSerializer(page, many=True).data)
        return Response(AttendanceSerializer(qs, many=True).data)

    def _validate_mark_body(self, data):
        staff_id = str(data.get("staffId", data.get("staff_id", "")) or "")
        if not staff_id:
            return None, "staffId required."
        day = _parse_date(data.get("date", ""))
        if day is None:
            return None, "Invalid date (YYYY-MM-DD)."
        st = str(data.get("status", "") or "")
        if st not in ("present", "absent", "half", "leave"):
            return None, "Invalid status."
        for key in ("inTime", "outTime"):
            raw_key = "in_time" if key == "inTime" else "out_time"
            val = data.get(key, data.get(raw_key, ""))
            if val not in (None, "") and not _valid_time(val):
                return None, f"Invalid {key} (HH:MM)."
        return {"staff_id": staff_id, "date": day, "status": st}, None

    @action(detail=False, methods=["post"], url_path="mark")
    def mark(self, request):
        """Upsert — same staff+date re-mark updates the row (UNIQUE guard)."""
        validated, err = self._validate_mark_body(request.data)
        if err:
            code = 404 if "staffId" in err and "required" not in err else 400
            return Response({"message": err}, status=code)
        if not StaffMember.objects.filter(pk=validated["staff_id"]).exists():
            return Response({"message": "Staff not found."}, status=404)
        data = request.data
        in_time = str(data.get("inTime", data.get("in_time", "")) or "")
        out_time = str(data.get("outTime", data.get("out_time", "")) or "")
        note = str(data.get("note", "") or "")
        row, created = Attendance.objects.update_or_create(
            staff_id=validated["staff_id"],
            date=validated["date"],
            defaults={
                "status": validated["status"],
                "in_time": in_time[:5],
                "out_time": out_time[:5],
                "note": note,
            },
        )
        return Response(AttendanceSerializer(row).data, status=201 if created else 200)

    @action(detail=False, methods=["post", "patch"], url_path="times")
    def times(self, request):
        """Update in/out/note/status of an EXISTING row — 404 if no hajira yet."""
        staff_id = str(request.data.get("staffId", request.data.get("staff_id", "")) or "")
        day = _parse_date(request.data.get("date", ""))
        if not staff_id or day is None:
            return Response({"message": "staffId + valid date required."}, status=400)
        row = Attendance.objects.filter(staff_id=staff_id, date=day).first()
        if row is None:
            return Response({"message": "Hajira not marked yet for this date."}, status=404)
        data = request.data
        if "status" in data:
            st = str(data["status"] or "")
            if st not in ("present", "absent", "half", "leave"):
                return Response({"message": "Invalid status."}, status=400)
            row.status = st
        for key, field in (("inTime", "in_time"), ("outTime", "out_time")):
            raw_key = field
            if key in data or raw_key in data:
                val = str(data.get(key, data.get(raw_key, "")) or "")
                if val and not _valid_time(val):
                    return Response({"message": f"Invalid {key} (HH:MM)."}, status=400)
                setattr(row, field, val[:5])
        if "note" in data:
            row.note = str(data["note"] or "")
        row.save()
        return Response(AttendanceSerializer(row).data)


# ------------------------------------------------------------- expenses ---


class ExpenseViewSet(viewsets.ModelViewSet):
    """GET/POST/PATCH (staff) / DELETE (admin only). Newest-first."""

    queryset = Expense.objects.all().order_by("-date", "-created_at")
    serializer_class = ExpenseSerializer
    http_method_names = ["get", "post", "patch", "put", "delete", "head", "options"]

    def get_permissions(self):
        if self.action == "destroy":
            return [IsAdmin()]
        return [IsStaff()]

    def create(self, request, *args, **kwargs):
        data = request.data
        try:
            amount = Decimal(str(data.get("amount", 0)))
        except Exception:
            return Response({"message": "Valid amount required."}, status=400)
        if amount <= 0:
            return Response({"message": "Amount must be > 0."}, status=400)
        category = str(data.get("category", "") or "").strip()[:30]
        if not category:
            return Response({"message": "Category required."}, status=400)
        day = _parse_date(data.get("date", "") or "") or _today()
        note = str(data.get("note", "") or "").strip()[:255] or category
        by = str(data.get("by", "") or "").strip()[:100] or getattr(request.user, "name", "")
        exp = Expense.objects.create(date=day, category=category, note=note, amount=amount, by=by)
        return Response(ExpenseSerializer(exp).data, status=201)

    def partial_update(self, request, *args, **kwargs):
        return self._patch(request, **kwargs)

    def update(self, request, *args, **kwargs):
        return self._patch(request, **kwargs)

    def _patch(self, request, **kwargs):
        exp = get_object_or_404(Expense, pk=kwargs["pk"])
        data = request.data
        if "amount" in data:
            try:
                amount = Decimal(str(data["amount"]))
            except Exception:
                return Response({"message": "Valid amount required."}, status=400)
            if amount <= 0:
                return Response({"message": "Amount must be > 0."}, status=400)
            exp.amount = amount
        if "category" in data:
            category = str(data["category"] or "").strip()[:30]
            if not category:
                return Response({"message": "Category required."}, status=400)
            exp.category = category
        if "date" in data:
            day = _parse_date(data["date"])
            if day is None:
                return Response({"message": "Invalid date (YYYY-MM-DD)."}, status=400)
            exp.date = day
        if "note" in data:
            exp.note = str(data["note"] or "").strip()[:255]
        exp.save()
        return Response(ExpenseSerializer(exp).data)


# --------------------------------------------------------------- salary ---


class SalaryViewSet(viewsets.GenericViewSet):
    """GET /api/salary?month= (staff) + POST /api/salary/pay (admin — money out)."""

    queryset = SalaryPayment.objects.all().select_related("staff").order_by("-date", "-created_at")
    serializer_class = SalaryPaymentSerializer
    permission_classes = [IsStaff]

    def list(self, request, *args, **kwargs):
        qs = self.get_queryset()
        month = request.query_params.get("month")
        staff_id = request.query_params.get("staffId", request.query_params.get("staff_id"))
        if staff_id:
            qs = qs.filter(staff_id=staff_id)
        if month:
            if not _parse_month(month):
                return Response({"message": "Invalid month (YYYY-MM)."}, status=400)
            qs = qs.filter(month=month)
        page = self.paginate_queryset(qs)
        if page is not None:
            return self.get_paginated_response(SalaryPaymentSerializer(page, many=True).data)
        return Response(SalaryPaymentSerializer(qs, many=True).data)

    @action(detail=False, methods=["post"], url_path="pay", permission_classes=[IsAdmin])
    def pay(self, request):
        data = request.data
        staff_id = str(data.get("staffId", data.get("staff_id", "")) or "")
        if not staff_id:
            return Response({"message": "staffId required."}, status=400)
        staff = StaffMember.objects.filter(pk=staff_id).first()
        if staff is None:
            return Response({"message": "Staff not found."}, status=404)
        month = _parse_month(data.get("month", ""))
        if not month:
            return Response({"message": "Valid month (YYYY-MM) required."}, status=400)
        try:
            amount = Decimal(str(data.get("amount", 0)))
        except Exception:
            return Response({"message": "Valid amount required."}, status=400)
        if amount <= 0:
            return Response({"message": "Amount must be > 0."}, status=400)
        pay = SalaryPayment.objects.create(
            staff=staff,
            month=month,
            amount=amount,
            note=str(data.get("note", "") or "").strip()[:255],
            date=_today(),
        )
        return Response(SalaryPaymentSerializer(pay).data, status=201)


# ---------------------------------------------------------------- hisab ---


class HisabSummaryView(APIView):
    """GET /api/hisab/summary?month=YYYY-MM&date=YYYY-MM-DD — 8 fixed aggregate queries.

    sales = paid orders, cancelled excluded. expenses exclude `salary` head
    (double-count guard — salary-paid lives in SalaryPayment, database.md §2.13).
    earned = present x 1 + half x 0.5, per-day = salary / 30 (JS Math.round parity).
    """

    permission_classes = [IsAdmin]

    def get(self, request):
        month = request.query_params.get("month") or _today().isoformat()[:7]
        if not _parse_month(month):
            return Response({"message": "Invalid month (YYYY-MM)."}, status=400)
        day_raw = request.query_params.get("date")
        day = _parse_date(day_raw) if day_raw else _today()
        if day is None:
            return Response({"message": "Invalid date (YYYY-MM-DD)."}, status=400)

        first, nxt = _month_range(month)
        tz = timezone.get_current_timezone()
        month_start = datetime(first.year, first.month, 1, tzinfo=tz)
        month_end = datetime(nxt.year, nxt.month, 1, tzinfo=tz)
        day_start = datetime(day.year, day.month, day.day, tzinfo=tz)
        day_end = day_start + timezone.timedelta(days=1)

        paid_q = Q(payment_status=Order.PaymentStatus.PAID) & ~Q(
            order_status=Order.OrderStatus.CANCELLED
        )
        # 1 — month sales
        month_sales = (
            Order.objects.filter(paid_q, created_at__gte=month_start, created_at__lt=month_end).aggregate(
                s=Sum("total_amount")
            )["s"]
            or Decimal("0")
        )
        # 2 — month expenses (salary head excluded)
        month_exp = (
            Expense.objects.filter(date__gte=first, date__lt=nxt)
            .exclude(category="salary")
            .aggregate(s=Sum("amount"))["s"]
            or Decimal("0")
        )
        # 3 — attendance grouped per staff (1 query, GROUP BY)
        att_rows = (
            Attendance.objects.filter(date__gte=first, date__lt=nxt)
            .values("staff_id")
            .annotate(
                present=Count(Case(When(status="present", then=1))),
                half=Count(Case(When(status="half", then=1))),
                absent=Count(Case(When(status="absent", then=1))),
                leave=Count(Case(When(status="leave", then=1))),
                days=Sum(
                    Case(
                        When(status="present", then=1.0),
                        When(status="half", then=0.5),
                        default=0.0,
                    )
                ),
            )
        )
        att_map = {row["staff_id"]: row for row in att_rows}
        # 4 — salary paid per staff, ledger month (1 query, GROUP BY)
        pay_rows = (
            SalaryPayment.objects.filter(month=month)
            .values("staff_id")
            .annotate(paid=Sum("amount"))
        )
        pay_map = {row["staff_id"]: row["paid"] for row in pay_rows}
        salary_paid = sum((v for v in pay_map.values()), Decimal("0"))
        # 5 — active staff (1 query)
        staff_list = list(StaffMember.objects.filter(active=True).order_by("created_at"))
        # 6/7/8 — today panel
        today_sales = (
            Order.objects.filter(paid_q, created_at__gte=day_start, created_at__lt=day_end).aggregate(
                s=Sum("total_amount")
            )["s"]
            or Decimal("0")
        )
        today_exp = (
            Expense.objects.filter(date=day).exclude(category="salary").aggregate(s=Sum("amount"))["s"]
            or Decimal("0")
        )
        today_sal = (
            SalaryPayment.objects.filter(date=day).aggregate(s=Sum("amount"))["s"] or Decimal("0")
        )

        due_by_staff = []
        payable_total = Decimal("0")
        for st in staff_list:
            agg = att_map.get(st.pk, {})
            days = float(agg.get("days") or 0)
            payable = _earned(st.monthly_salary, days)
            paid = pay_map.get(st.pk) or Decimal("0")
            due = Decimal(payable) - paid
            payable_total += Decimal(payable)
            due_by_staff.append(
                {
                    "staffId": str(st.pk),
                    "name": st.name,
                    "present": agg.get("present") or 0,
                    "half": agg.get("half") or 0,
                    "absent": agg.get("absent") or 0,
                    "leave": agg.get("leave") or 0,
                    "payable": payable,
                    "paid": float(paid),
                    "due": float(due),
                }
            )

        cash = month_sales - month_exp - salary_paid
        return Response(
            {
                "month": month,
                "sales": float(month_sales),
                "expenses": float(month_exp),
                "salaryPaid": float(salary_paid),
                "cash": float(cash),
                "payableTotal": float(payable_total),
                "dueTotal": float(payable_total - salary_paid),
                "dueByStaff": due_by_staff,
                "today": {
                    "date": day.isoformat(),
                    "sales": float(today_sales),
                    "expenses": float(today_exp),
                    "salaryPaid": float(today_sal),
                    "cash": float(today_sales - today_exp - today_sal),
                },
            }
        )
