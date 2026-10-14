"""Contract layer — frontend field names fixed, DB names never leak."""

from rest_framework import serializers

from core.serializers import BhojBilashSerializer

from .models import FoodItem, Package


class FoodSerializer(BhojBilashSerializer):
    # Decimal → JSON number (DRF default is string — contract wants number)
    price = serializers.SerializerMethodField()

    class Meta:
        model = FoodItem
        fields = ("_id", "name", "category", "price", "image", "available", "createdAt")

    def get_price(self, obj) -> float:
        return float(obj.price)


class FoodWriteSerializer(serializers.ModelSerializer):
    """POST/PATCH input — same rules as frontend addFood/updateFood."""

    class Meta:
        model = FoodItem
        fields = ("name", "category", "price", "image", "available")
        extra_kwargs = {
            "name": {"required": False},
            "category": {"required": False},
            "price": {"required": False},
            "image": {"required": False},
            "available": {"required": False},
        }

    def validate_name(self, value: str) -> str:
        if not value.strip():
            raise serializers.ValidationError("Name required.")
        return value.strip()


class PackageItemIn(serializers.Serializer):
    """Frontend shape: { foodId, qty }."""

    foodId = serializers.CharField()
    qty = serializers.IntegerField(min_value=1)


class PackageSerializer(BhojBilashSerializer):
    items = serializers.SerializerMethodField()
    price = serializers.SerializerMethodField()
    offerPrice = serializers.SerializerMethodField()
    offerNote = serializers.SerializerMethodField()
    image = serializers.SerializerMethodField()
    effectivePrice = serializers.SerializerMethodField()

    class Meta:
        model = Package
        fields = (
            "_id",
            "name",
            "items",
            "price",
            "offerPrice",
            "offerNote",
            "image",
            "active",
            "createdAt",
            "effectivePrice",
        )

    def get_items(self, obj) -> list:
        # prefetched items__food — no extra queries
        out = []
        for line in getattr(obj, "items").all():
            out.append({"foodId": line.food_id, "qty": line.qty})
        return out

    def get_price(self, obj) -> float:
        return float(obj.price)

    def get_offerPrice(self, obj):
        if obj.offer_price is None:
            return None
        return float(obj.offer_price)

    def get_offerNote(self, obj):
        return obj.offer_note or None

    def get_image(self, obj):
        return obj.image or None

    def get_effectivePrice(self, obj) -> float:
        return float(obj.effective_price)
