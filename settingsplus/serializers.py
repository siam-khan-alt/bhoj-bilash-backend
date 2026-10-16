"""Settingsplus contract — frontend shapes preserved exactly (key/sort/hours index)."""

from rest_framework import serializers

from core.serializers import BhojBilashSerializer

from .models import OpeningHours, OptionList, RestaurantConfig, Review


class DayHoursOut(serializers.Serializer):
    open = serializers.CharField()
    close = serializers.CharField()
    closed = serializers.BooleanField(default=False)

    def to_representation(self, instance: OpeningHours) -> dict:
        data = {
            "open": instance.open_time.strftime("%H:%M"),
            "close": instance.close_time.strftime("%H:%M"),
        }
        if instance.closed:
            data["closed"] = True
        return data


class ConfigOut(serializers.Serializer):
    """Matches frontend RestaurantConfig + extra isOpenNow (server-computed)."""

    slug = serializers.CharField()
    name = serializers.CharField()
    logo = serializers.CharField(allow_null=True)
    address = serializers.CharField(allow_null=True)
    phone = serializers.CharField(allow_null=True)
    hours = DayHoursOut(many=True)
    isOpenNow = serializers.BooleanField()


class OptionSerializer(BhojBilashSerializer):
    key = serializers.CharField(source="list_key")
    sort = serializers.IntegerField(source="sort_order")

    class Meta:
        model = OptionList
        fields = ("_id", "key", "value", "label_bn", "label_en", "sort", "active", "createdAt")


class ReviewSerializer(BhojBilashSerializer):
    class Meta:
        model = Review
        fields = ("_id", "name", "rating", "text", "createdAt")
