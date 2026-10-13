"""Shared contract layer — every API object exposes `_id` (string) + `createdAt` (ISO)."""

from rest_framework import serializers


class BhojBilashSerializer(serializers.ModelSerializer):
    """Base for models with `created_at`. DB names never leak — camelCase out."""

    _id = serializers.SerializerMethodField()
    createdAt = serializers.SerializerMethodField()

    def get__id(self, obj) -> str:
        return str(obj.pk)

    def get_createdAt(self, obj) -> str | None:
        dt = getattr(obj, "created_at", None)
        return dt.isoformat() if dt else None
