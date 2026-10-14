"""Orders views — 3-query create, 3-query list page, server-trust money."""

from decimal import Decimal

from django.db import transaction
from django.db.models import Count, Sum
from django.shortcuts import get_object_or_404
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from core.permissions import IsAdmin, IsStaff
from menu.models import FoodItem

from .models import Order, OrderItem
from .serializers import OrderLineIn, OrderSerializer, synthesize_customer


def _extract_phone(data: dict) -> str:
    """Accept customerPhone OR legacy POS customer object (email prefix)."""
    phone = str(data.get("customerPhone", "") or "").strip()
    if phone:
        return phone[:20]
    customer = data.get("customer") or {}
    email = str(customer.get("email", "") or "")
    if "@pos.local" in email:
        prefix = email.split("@")[0].strip()
        if prefix and prefix != "walkin":
            return prefix[:20]
    name = str(customer.get("name", "") or "")
    if name.startswith("Walk-in"):
        rest = name.replace("Walk-in", "").strip().split()[0] if name.strip() else ""
        if rest and rest not in ("customer",):
            return rest.strip("()")[:20]
    return ""


class OrderViewSet(viewsets.ModelViewSet):
    """POST create (staff) / GET list+retrieve (staff) / status PATCH (admin)."""

    queryset = (
        Order.objects.all()
        .select_related("created_by")
        .prefetch_related("items__food_item")
        .order_by("-created_at")
    )
    serializer_class = OrderSerializer
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_permissions(self):
        if self.action in ("list", "retrieve", "by_phone"):
            return [IsStaff()]
        if self.action in ("partial_update", "update", "order_status"):
            # status flow is admin-only (Dhap 3 spec)
            return [IsAdmin()]
        if self.action == "create":
            return [IsStaff()]
        if self.action == "destroy":
            return [IsAdmin()]
        return [IsStaff()]

    def create(self, request, *args, **kwargs):
        data = request.data
        raw_items = data.get("items", [])
        if not raw_items:
            return Response({"message": "Order needs at least 1 item."}, status=400)
        if len(raw_items) > 100:
            return Response({"message": "Too many lines (max 100)."}, status=400)

        line_ser = OrderLineIn(data=raw_items, many=True)
        try:
            line_ser.is_valid(raise_exception=True)
        except Exception:
            return Response(
                {"message": "Each item needs {foodItemId, quantity>0}."}, status=400
            )
        lines = line_ser.validated_data

        order_type = str(data.get("orderType", "dine_in") or "dine_in")
        if order_type not in ("dine_in", "parcel", "both"):
            return Response({"message": "Invalid order type."}, status=400)

        phone = _extract_phone(data if isinstance(data, dict) else {})

        # 1 query — bulk food fetch (IN), server-trust prices
        real_ids = [
            ln["foodItemId"]
            for ln in lines
            if not str(ln["foodItemId"]).startswith("pkgline_")
        ]
        foods = FoodItem.objects.in_bulk(real_ids) if real_ids else {}

        subtotal = Decimal("0")
        built = []
        for ln in lines:
            fid = str(ln["foodItemId"])
            qty = int(ln["quantity"])
            if fid.startswith("pkgline_"):
                # package pseudo-line — label + price REQUIRED
                label = str(ln.get("label", "") or "").strip()
                if not label:
                    return Response(
                        {"message": f"Item {fid} needs a label."}, status=400
                    )
                if ln.get("price") is None:
                    return Response(
                        {"message": f"Item {fid} needs a price."}, status=400
                    )
                unit = Decimal(str(ln["price"]))
                built.append((None, label[:150], qty, unit))
                subtotal += unit * qty
            else:
                food = foods.get(fid)
                if food is None:
                    return Response(
                        {"message": f"Item {fid} not found."}, status=400
                    )
                unit = food.price
                built.append((food, food.name, qty, unit))
                subtotal += unit * qty

        try:
            discount_in = Decimal(str(data.get("discount", 0) or 0))
        except Exception:
            return Response({"message": "Invalid discount."}, status=400)
        if discount_in < 0:
            discount_in = Decimal("0")
        discount = min(discount_in, subtotal)
        total = subtotal - discount

        payment_method = str(data.get("paymentMethod", "cash") or "cash")
        if payment_method not in ("cash", "card"):
            payment_method = "cash"

        with transaction.atomic():
            order = Order.objects.create(
                created_by=request.user,
                customer_phone=phone or None,
                order_type=order_type,
                order_status=Order.OrderStatus.PLACED,
                payment_status=Order.PaymentStatus.PAID,
                payment_method=payment_method,
                discount=discount,
                total_amount=total,
            )
            OrderItem.objects.bulk_create(
                [
                    OrderItem(
                        order=order,
                        food_item=food,
                        item_name=name,
                        quantity=qty,
                        price=unit,
                    )
                    for food, name, qty, unit in built
                ]
            )

        order = self.get_queryset().get(pk=order.pk)
        return Response({"order": OrderSerializer(order).data}, status=201)

    def partial_update(self, request, *args, **kwargs):
        # only status changes here — money/customer immutable after bill
        order = get_object_or_404(Order, pk=kwargs["pk"])
        new_status = request.data.get("orderStatus", request.data.get("status", ""))
        allowed = ("placed", "preparing", "delivered", "cancelled")
        if new_status not in allowed:
            return Response({"message": "Invalid order status."}, status=400)
        order.order_status = new_status
        order.save(update_fields=["order_status", "updated_at"])
        order = self.get_queryset().get(pk=order.pk)
        return Response(OrderSerializer(order).data)

    @action(
        detail=True,
        methods=["patch"],
        url_path="status",
        permission_classes=[IsAdmin],
    )
    def order_status(self, request, pk=None):
        """PATCH /api/orders/:id/status — admin-only kitchen flow."""
        return self.partial_update(request, pk=pk)

    def update(self, request, *args, **kwargs):
        return self.partial_update(request, *args, **kwargs)

    @action(detail=False, methods=["get"], url_path="by-phone")
    def by_phone(self, request):
        """Group repeat buyers by phone — POS ids are random per bill (§5)."""
        phone = str(request.query_params.get("phone", "") or "").strip()
        if not phone:
            return Response({"message": "phone query required."}, status=400)
        qs = (
            Order.objects.filter(customer_phone=phone)
            .select_related("created_by")
            .prefetch_related("items__food_item")
            .order_by("-created_at")
        )
        orders = list(qs[:100])
        agg = Order.objects.filter(customer_phone=phone).aggregate(
            total=Count("id"),
            spent=Sum("total_amount", filter=models_Q_paid()),
        )
        spent = agg["spent"] or Decimal("0")
        first = orders[0] if orders else None
        customer = (
            synthesize_customer(first)
            if first
            else {"_id": "", "name": f"Walk-in {phone}", "email": f"{phone}@pos.local"}
        )
        return Response(
            {
                "customer": customer,
                "totalOrders": agg["total"] or 0,
                "totalSpent": float(spent),
                "orders": OrderSerializer(orders, many=True).data,
            }
        )


def models_Q_paid():
    from django.db import models

    return models.Q(payment_status=Order.PaymentStatus.PAID)
