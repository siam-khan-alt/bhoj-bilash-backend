"""Settingsplus views — shop config + hours + option master-data + public reviews.

Query budgets (fixed):
- GET /api/config ............ 2 queries (config row + 7 hours; first-ever GET seeds defaults)
- PATCH /api/config .......... 2-4 queries (fetch hours + bulk_update 7 + optional config save)
- GET /api/options?key= ...... 1 query ((list_key,sort) index, sort-ordered)
- POST /api/options ........... 3 queries (dup check + max sort + insert)
- PATCH /api/options/:id ..... ≤4 queries (fetch + dup check + save + 0/1 cascade UPDATE)
- DELETE /api/options/:id .... 2 queries (fetch + EXISTS guard; blocked deletes never touch data)
- GET /api/reviews ............ 1 query + COUNT (paginator)
- POST /api/reviews ........... 2 queries (throttle check is cache, not DB + insert)
- GET /api/reviews/stats ..... 1 aggregate query

Guards (senior call):
- Locked values (expense_head:salary, food_category:Drinks/Juice) — label/sort/active
  may change, value rename/delete → 400. Reports depend on these codes.
- Rename cascades server-side in ONE atomic block (frontend used to fire N calls).
- Referenced value delete → 400 naming where it is used.
- Reviews: public POST but throttled 5/hour/IP (spam guard) → 429 on 6th.

Frontend mapping (adapter swaps inside lib/api/* only):
- getRestaurantConfig/updateRestaurantConfig .. GET/PATCH /api/config
- isOpenNow ............................... server field `isOpenNow` (same rule)
- get/add/update/deleteOption ............. /api/options?key= + CRUD
- LOCKED_VALUES ........................... mirrored here as LOCKED
- get/addReview ........................... GET/POST /api/reviews (+ stats endpoint)
"""

import re
from datetime import time as dtime

from django.db import transaction
from django.db.models import Avg, Count
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView

from core.permissions import IsAdmin
from khata.models import Expense, StaffMember
from menu.models import FoodItem

from .models import OpeningHours, OptionList, RestaurantConfig, Review
from .serializers import ConfigOut, OptionSerializer, ReviewSerializer

TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")

#: Structural values — reports/logic depend on the CODE (database.md §2.13).
LOCKED = {
    "expense_head": {"salary"},
    "food_category": {"Drinks", "Juice"},
}

#: Rename cascade targets: option key -> (model, plain-string column).
CASCADE = {
    "food_category": (FoodItem, "category", "food items"),
    "staff_job": (StaffMember, "job", "staff members"),
    "expense_head": (Expense, "category", "expenses"),
    # payment_method / drink_size have no stored references yet — row-only rename.
}

DEFAULT_HOURS = [
    ("09:00", "22:00"),  # 0 Sunday
    ("09:00", "22:00"),  # 1 Monday
    ("09:00", "22:00"),  # 2
    ("09:00", "22:00"),  # 3
    ("09:00", "22:00"),  # 4
    ("09:00", "23:00"),  # 5 Friday — 1h later
    ("09:00", "22:00"),  # 6 Saturday
]


def _to_min(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def ensure_defaults() -> tuple[RestaurantConfig, list]:
    """Singleton + 7 hour rows always exist (first GET seeds them)."""
    config, _ = RestaurantConfig.objects.get_or_create(
        id=1,
        defaults={
            "slug": "bhoj-bilash",
            "name": "Bhoj Bilash",
            "logo": "/logo.png",
            "address": "Dhaka, Bangladesh",
            "phone": "+880 1700-000001",
        },
    )
    hours = list(OpeningHours.objects.all().order_by("weekday"))
    if len(hours) < 7:
        have = {h.weekday for h in hours}
        OpeningHours.objects.bulk_create(
            [
                OpeningHours(
                    weekday=i,
                    open_time=dtime(*map(int, o.split(":"))),
                    close_time=dtime(*map(int, c.split(":"))),
                )
                for i, (o, c) in enumerate(DEFAULT_HOURS)
                if i not in have
            ]
        )
        hours = list(OpeningHours.objects.all().order_by("weekday"))
    return config, hours


def is_open_now(hours: list, now=None) -> bool:
    """Mirror of frontend isOpenNow: today's row, not closed, open <= now < close."""
    if now is None:
        now = timezone.localtime()
    if len(hours) != 7:
        return False
    today = hours[now.isoweekday() % 7]  # isoweekday()%7 == JS getDay() (Sun=0)
    if today.closed:
        return False
    cur = now.hour * 60 + now.minute
    return _to_min(today.open_time.strftime("%H:%M")) <= cur < _to_min(
        today.close_time.strftime("%H:%M")
    )


# ---------------------------------------------------------------- config ---


class ConfigView(APIView):
    """GET /api/config (public) / PATCH /api/config (admin)."""

    def get_permissions(self):
        if self.request.method == "PATCH":
            return [IsAdmin()]
        return [AllowAny()]

    def get(self, request):
        config, hours = ensure_defaults()
        return Response(
            ConfigOut(
                {
                    "slug": config.slug,
                    "name": config.name,
                    "logo": config.logo,
                    "address": config.address,
                    "phone": config.phone,
                    "hours": hours,
                    "isOpenNow": is_open_now(hours),
                }
            ).data
        )

    def patch(self, request):
        config, hours = ensure_defaults()
        data = request.data
        if "name" in data:
            name = str(data["name"] or "").strip()
            if not name:
                return Response({"message": "Shop name required."}, status=400)
            config.name = name[:100]
        if "slug" in data:
            config.slug = str(data["slug"] or "").strip()[:50] or config.slug
        if "logo" in data:
            config.logo = str(data["logo"] or "").strip()[:500] or None
        if "address" in data:
            config.address = str(data["address"] or "").strip()[:255] or None
        if "phone" in data:
            config.phone = str(data["phone"] or "").strip()[:20] or None
        config.save()

        if "hours" in data:
            days = data["hours"]
            if isinstance(days, dict):  # accept {weekday: {...}} too
                days = [days.get(str(i), days.get(i)) for i in range(7)]
            if not isinstance(days, list) or len(days) != 7 or any(d is None for d in days):
                return Response({"message": "hours needs 7 day entries."}, status=400)
            parsed = []
            for i, d in enumerate(days):
                o, c = str(d.get("open", "")), str(d.get("close", ""))
                if not TIME_RE.match(o) or not TIME_RE.match(c):
                    return Response(
                        {"message": f"Day {i}: open/close must be HH:MM."}, status=400
                    )
                if _to_min(c) <= _to_min(o):
                    return Response(
                        {"message": f"Day {i}: close must be after open."}, status=400
                    )
                parsed.append((o, c, bool(d.get("closed", False))))
            by_day = {h.weekday: h for h in hours}
            for i, (o, c, closed) in enumerate(parsed):
                row = by_day[i]
                row.open_time = dtime(*map(int, o.split(":")))
                row.close_time = dtime(*map(int, c.split(":")))
                row.closed = closed
            with transaction.atomic():
                OpeningHours.objects.bulk_update(
                    [by_day[i] for i in range(7)], ["open_time", "close_time", "closed"]
                )
            hours = [by_day[i] for i in range(7)]

        return Response(
            ConfigOut(
                {
                    "slug": config.slug,
                    "name": config.name,
                    "logo": config.logo,
                    "address": config.address,
                    "phone": config.phone,
                    "hours": hours,
                    "isOpenNow": is_open_now(hours),
                }
            ).data
        )


# ---------------------------------------------------------------- options ---


class OptionViewSet(viewsets.GenericViewSet):
    """GET /api/options?key= (public) + POST/PATCH/DELETE (admin, locked + cascade)."""

    queryset = OptionList.objects.all().order_by("sort_order")
    serializer_class = OptionSerializer

    def get_permissions(self):
        if self.action == "list":
            return [AllowAny()]
        return [IsAdmin()]

    def list(self, request, *args, **kwargs):
        key = request.query_params.get("key")
        if key not in OptionList.ListKey.values:
            return Response({"message": "Valid ?key= required."}, status=400)
        qs = self.get_queryset().filter(list_key=key)
        active = request.query_params.get("active")
        if active in ("1", "true", "True"):
            qs = qs.filter(active=True)
        elif active in ("0", "false", "False"):
            qs = qs.filter(active=False)
        return Response(OptionSerializer(qs, many=True).data)

    def create(self, request, *args, **kwargs):
        data = request.data
        key = str(data.get("key", data.get("list_key", "")) or "")
        if key not in OptionList.ListKey.values:
            return Response({"message": "Valid key required."}, status=400)
        value = str(data.get("value", "") or "").strip()[:50]
        if not value:
            return Response({"message": "Value required."}, status=400)
        if OptionList.objects.filter(list_key=key, value__iexact=value).exists():
            return Response({"message": "This value already exists."}, status=400)
        from django.db.models import Max

        top = OptionList.objects.filter(list_key=key).aggregate(m=Max("sort_order"))["m"] or 0
        row = OptionList.objects.create(
            list_key=key,
            value=value,
            label_bn=str(data.get("label_bn", "") or "").strip()[:100] or value,
            label_en=str(data.get("label_en", "") or "").strip()[:100] or value,
            sort_order=int(data.get("sort", data.get("sort_order", top + 1)) or 0),
            active=True,
        )
        return Response(OptionSerializer(row).data, status=201)

    def partial_update(self, request, *args, **kwargs):
        return self._patch(request, **kwargs)

    def update(self, request, *args, **kwargs):
        return self._patch(request, **kwargs)

    def _patch(self, request, **kwargs):
        row = get_object_or_404(OptionList, pk=kwargs["pk"])
        data = request.data
        cascade = None  # (model, field, old, new) — applied atomically with self save
        if "value" in data:
            new_value = str(data["value"] or "").strip()[:50]
            if not new_value:
                return Response({"message": "Value required."}, status=400)
            if new_value != row.value:
                if row.value in LOCKED.get(row.list_key, set()):
                    return Response(
                        {"message": "This value is locked — label can change, value cannot."},
                        status=400,
                    )
                if (
                    OptionList.objects.filter(list_key=row.list_key, value__iexact=new_value)
                    .exclude(pk=row.pk)
                    .exists()
                ):
                    return Response({"message": "This value already exists."}, status=400)
                target = CASCADE.get(row.list_key)
                if target:
                    model, field, _ = target
                    cascade = (model, field, row.value, new_value)
                row.value = new_value
        if "label_bn" in data:
            row.label_bn = str(data["label_bn"] or "").strip()[:100] or row.value
        if "label_en" in data:
            row.label_en = str(data["label_en"] or "").strip()[:100] or row.value
        if "sort" in data or "sort_order" in data:
            try:
                row.sort_order = int(data.get("sort", data.get("sort_order")))
            except (TypeError, ValueError):
                return Response({"message": "sort must be a number."}, status=400)
        if "active" in data:
            row.active = bool(data["active"])
        if cascade:
            model, field, old, new = cascade
            with transaction.atomic():
                row.save()
                model.objects.filter(**{field: old}).update(**{field: new})
        else:
            row.save()
        return Response(OptionSerializer(row).data)

    def destroy(self, request, *args, **kwargs):
        row = get_object_or_404(OptionList, pk=kwargs["pk"])
        if row.value in LOCKED.get(row.list_key, set()):
            return Response(
                {"message": "This value is locked and cannot be deleted."}, status=400
            )
        target = CASCADE.get(row.list_key)
        if target:
            model, field, label = target
            used = model.objects.filter(**{field: row.value}).count()
            if used:
                return Response(
                    {"message": f"Cannot delete — used in {used} {label}."}, status=400
                )
        row.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------- reviews ---


class ReviewPostThrottle(AnonRateThrottle):
    """Spam guard — 5 reviews/hour per IP, 6th → 429."""

    rate = "5/hour"


class ReviewViewSet(viewsets.ModelViewSet):
    """GET (public, newest-first) / POST (public, throttled) / DELETE (admin)."""

    queryset = Review.objects.all().order_by("-created_at")
    serializer_class = ReviewSerializer
    http_method_names = ["get", "post", "delete", "head", "options"]

    def get_permissions(self):
        if self.action == "destroy":
            return [IsAdmin()]
        return [AllowAny()]

    def get_throttles(self):
        if self.action == "create":
            return [ReviewPostThrottle()]
        return []

    def create(self, request, *args, **kwargs):
        data = request.data
        name = str(data.get("name", "") or "").strip()
        text = str(data.get("text", "") or "").strip()
        if not name or not text:
            return Response({"message": "Name and review text required."}, status=400)
        if len(name) > 40:
            return Response({"message": "Name too long (max 40)."}, status=400)
        if len(text) > 300:
            return Response({"message": "Review too long (max 300)."}, status=400)
        try:
            rating = int(data.get("rating", 0))
        except (TypeError, ValueError):
            return Response({"message": "Rating must be 1–5."}, status=400)
        if rating < 1 or rating > 5:
            return Response({"message": "Rating must be 1–5."}, status=400)
        rev = Review.objects.create(name=name[:40], rating=rating, text=text[:300])
        return Response(ReviewSerializer(rev).data, status=201)

    @action(detail=False, methods=["get"], url_path="stats")
    def stats(self, request):
        """Home page average + count — 1 aggregate query."""
        agg = Review.objects.aggregate(average=Avg("rating"), count=Count("id"))
        return Response(
            {
                "average": round(float(agg["average"] or 0), 2),
                "count": agg["count"] or 0,
            }
        )
