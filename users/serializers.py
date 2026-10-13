from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from .models import User


class UserBriefSerializer(serializers.ModelSerializer):
    """Contract: {_id, name, email, role, createdAt} — password never leaves the server."""

    _id = serializers.SerializerMethodField()
    createdAt = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ("_id", "name", "email", "role", "createdAt")

    def get__id(self, obj) -> str:
        return str(obj.pk)

    def get_createdAt(self, obj) -> str | None:
        return obj.date_joined.isoformat() if obj.date_joined else None


class LoginSerializer(TokenObtainPairSerializer):
    """SimpleJWT returns access/refresh — contract wants {user, token}."""

    def validate(self, attrs):
        data = super().validate(attrs)
        data["token"] = data.pop("access")
        data.pop("refresh", None)
        data["user"] = UserBriefSerializer(self.user).data
        return data
