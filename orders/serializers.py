"""Order contract — customer synthesized, package pseudo foodItem, money as numbers."""

from rest_framework import serializers

from core.serializers import BhojBilashSerializer

from .models import Order


def synthesize_customer(order: Order) -> dict:
    """Same strings POS builds — no frontend change needed (database.md §2.5)."""
    phone = order.customer_phone or ""
    label = f"Walk-in {phone}" if phone else "Walk-in customer"
    email = f"{phone}@pos.local" if phone else "walkin@pos.local"
    return {"_id": str(order.created_by_id), "name": label, "email": email}


class OrderItemOut(serializers.Serializer):
    foodItem = serializers.SerializerMethodField()
    quantity = serializers.IntegerField()
    price = serializers.SerializerMethodField()

    def get_foodItem(self, obj) -> dict:
        if obj.food_item_id and getattr(obj, "food_item", None):
            f = obj.food_item
            return {
                "_id": str(f.pk),
                "name": f.name,
                "category": f.category,
                "price": float(f.price),
                "image": f.image or "",
                "available": f.available,
            }
        # package pseudo-line — frontend expects category "Package"
        return {
            "_id": obj.item_name and f"pkgline_{obj.pk}" or f"pkgline_{obj.pk}",
            "name": obj.item_name,
            "category": "Package",
            "price": float(obj.price),
            "image": "",
            "available": True,
        }

    def get_price(self, obj) -> float:
        return float(obj.price)


class OrderSerializer(BhojBilashSerializer):
    customer = serializers.SerializerMethodField()
    items = OrderItemOut(many=True, read_only=True)
    totalAmount = serializers.SerializerMethodField()
    orderStatus = serializers.CharField(source="order_status")
    paymentStatus = serializers.CharField(source="payment_status")
    orderType = serializers.CharField(source="order_type")

    class Meta:
        model = Order
        fields = (
            "_id",
            "customer",
            "items",
            "totalAmount",
            "discount",
            "orderStatus",
            "paymentStatus",
            "orderType",
            "createdAt",
        )

    def get_customer(self, obj) -> dict:
        return synthesize_customer(obj)

    def get_totalAmount(self, obj) -> float:
        return float(obj.total_amount)

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["discount"] = float(instance.discount)
        return data


class OrderLineIn(serializers.Serializer):
    foodItemId = serializers.CharField()
    quantity = serializers.IntegerField(min_value=1, max_value=100)
    label = serializers.CharField(required=False, allow_blank=True, default="")
    price = serializers.FloatField(required=False, min_value=0)
