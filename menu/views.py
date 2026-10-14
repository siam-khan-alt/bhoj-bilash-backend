"""Menu views — public reads, admin writes. Query budgets in docstrings."""

from django.db.models import ProtectedError
from rest_framework import status, viewsets
from rest_framework.response import Response

from core.permissions import IsAdmin

from .models import FoodItem, Package, PackageItem
from .serializers import FoodSerializer, FoodWriteSerializer, PackageItemIn, PackageSerializer


class FoodViewSet(viewsets.ModelViewSet):
    """GET /api/foods — 1 query. CRUD — admin only, O(1) PK lookup."""

    queryset = FoodItem.objects.all().order_by("-created_at")
    serializer_class = FoodSerializer

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return []
        return [IsAdmin()]

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            return FoodWriteSerializer
        return FoodSerializer

    def list(self, request, *args, **kwargs):
        qs = self.get_queryset()
        available = request.query_params.get("available")
        if available is not None:
            if available in ("1", "true", "True"):
                qs = qs.filter(available=True)
            elif available in ("0", "false", "False"):
                qs = qs.filter(available=False)
        page = self.paginate_queryset(qs)
        if page is not None:
            return self.get_paginated_response(FoodSerializer(page, many=True).data)
        return Response(FoodSerializer(qs, many=True).data)

    def create(self, request, *args, **kwargs):
        data = request.data
        if not str(data.get("name", "")).strip():
            return Response({"message": "Name required."}, status=400)
        if not str(data.get("category", "")).strip():
            return Response({"message": "Category required."}, status=400)
        try:
            price = float(data.get("price", -1))
        except (TypeError, ValueError):
            return Response({"message": "Valid price required."}, status=400)
        if price < 0:
            return Response({"message": "Price must be >= 0."}, status=400)
        ser = FoodWriteSerializer(data=data)
        ser.is_valid(raise_exception=True)
        food = FoodItem.objects.create(
            name=str(data["name"]).strip(),
            category=str(data["category"]).strip(),
            price=price,
            image=str(data.get("image", "") or ""),
            available=bool(data.get("available", True)),
        )
        return Response(FoodSerializer(food).data, status=201)

    def update(self, request, *args, **kwargs):
        return self._patch(request, partial=False, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        return self._patch(request, partial=True, **kwargs)

    def _patch(self, request, partial, **kwargs):
        from django.shortcuts import get_object_or_404

        food = get_object_or_404(FoodItem, pk=kwargs["pk"])
        data = request.data
        patch = {}
        if "name" in data:
            if not str(data["name"]).strip():
                return Response({"message": "Name required."}, status=400)
            patch["name"] = str(data["name"]).strip()
        if "category" in data:
            patch["category"] = str(data["category"]).strip()
        if "price" in data:
            try:
                price = float(data["price"])
            except (TypeError, ValueError):
                return Response({"message": "Valid price required."}, status=400)
            if price < 0:
                return Response({"message": "Price must be >= 0."}, status=400)
            patch["price"] = price
        if "image" in data:
            patch["image"] = str(data["image"] or "")
        if "available" in data:
            patch["available"] = bool(data["available"])
        for k, v in patch.items():
            setattr(food, k, v)
        food.save(update_fields=list(patch.keys()) or None)
        return Response(FoodSerializer(food).data)

    def destroy(self, request, *args, **kwargs):
        from django.shortcuts import get_object_or_404

        food = get_object_or_404(FoodItem, pk=kwargs["pk"])
        try:
            food.delete()
        except ProtectedError:
            return Response(
                {"message": "Food is used in a package — remove it from packages first."},
                status=400,
            )
        return Response(status=status.HTTP_204_NO_CONTENT)


class PackageViewSet(viewsets.ModelViewSet):
    """GET /api/packages — 2 queries constant (packages + prefetch items__food)."""

    queryset = Package.objects.all().order_by("-created_at").prefetch_related("items__food")
    serializer_class = PackageSerializer

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return []
        return [IsAdmin()]

    def get_queryset(self):
        qs = super().get_queryset()
        active = self.request.query_params.get("active")
        if active is not None and self.action == "list":
            if active in ("1", "true", "True"):
                qs = qs.filter(active=True)
            elif active in ("0", "false", "False"):
                qs = qs.filter(active=False)
        return qs

    def _save_items(self, package: Package, items: list) -> None:
        """Replace bundle lines — validated food FKs, unique per food."""
        package.items.all().delete()
        seen = set()
        bulk = []
        for row in items:
            fid = row["foodId"]
            if fid in seen:
                continue
            seen.add(fid)
            bulk.append(
                PackageItem(package=package, food_id=fid, qty=row["qty"])
            )
        PackageItem.objects.bulk_create(bulk)

    def _validate_package_payload(self, data, partial=False):
        if not partial or "name" in data:
            if not str(data.get("name", "")).strip():
                return "Package name required."
        if not partial or "items" in data:
            items = data.get("items", [])
            if not items:
                return "Package needs at least 1 item."
            ser = PackageItemIn(data=items, many=True)
            try:
                ser.is_valid(raise_exception=True)
            except Exception:
                return "Each item needs {foodId, qty>0}."
            food_ids = [r["foodId"] for r in ser.validated_data]
            found = set(
                FoodItem.objects.filter(pk__in=food_ids).values_list("pk", flat=True)
            )
            missing = [f for f in food_ids if f not in found]
            if missing:
                return f"Food not found: {', '.join(missing[:3])}."
        if not partial or "price" in data:
            try:
                price = float(data.get("price", -1))
            except (TypeError, ValueError):
                return "Valid price required."
            if price <= 0:
                return "Price must be > 0."
        if "offerPrice" in data and data["offerPrice"] not in (None, ""):
            try:
                op = float(data["offerPrice"])
            except (TypeError, ValueError):
                return "Valid offer price required."
            if op < 0:
                return "Offer price must be >= 0."
        return None

    def create(self, request, *args, **kwargs):
        err = self._validate_package_payload(request.data)
        if err:
            return Response({"message": err}, status=400)
        data = request.data
        offer = data.get("offerPrice")
        pkg = Package.objects.create(
            name=str(data["name"]).strip(),
            price=float(data["price"]),
            offer_price=float(offer) if offer not in (None, "") else None,
            offer_note=str(data.get("offerNote", "") or "").strip() or None,
            image=str(data.get("image", "") or "").strip(),
            active=True,
        )
        ser_items = PackageItemIn(data=data["items"], many=True)
        ser_items.is_valid(raise_exception=True)
        self._save_items(pkg, ser_items.validated_data)
        pkg = self.get_queryset().get(pk=pkg.pk)
        return Response(PackageSerializer(pkg).data, status=201)

    def partial_update(self, request, *args, **kwargs):
        from django.shortcuts import get_object_or_404

        pkg = get_object_or_404(Package, pk=kwargs["pk"])
        err = self._validate_package_payload(request.data, partial=True)
        if err:
            return Response({"message": err}, status=400)
        data = request.data
        if "name" in data:
            pkg.name = str(data["name"]).strip()
        if "price" in data:
            pkg.price = float(data["price"])
        if "offerPrice" in data:
            offer = data["offerPrice"]
            pkg.offer_price = float(offer) if offer not in (None, "") else None
        if "offerNote" in data:
            pkg.offer_note = str(data["offerNote"] or "").strip() or None
        if "image" in data:
            pkg.image = str(data["image"] or "").strip()
        if "active" in data:
            pkg.active = bool(data["active"])
        pkg.save()
        if "items" in data:
            ser_items = PackageItemIn(data=data["items"], many=True)
            ser_items.is_valid(raise_exception=True)
            self._save_items(pkg, ser_items.validated_data)
        pkg = self.get_queryset().get(pk=pkg.pk)
        return Response(PackageSerializer(pkg).data)

    def update(self, request, *args, **kwargs):
        return self.partial_update(request, *args, **kwargs)
