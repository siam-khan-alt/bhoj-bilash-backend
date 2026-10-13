from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.views import TokenObtainPairView

from .serializers import LoginSerializer, UserBriefSerializer


class LoginView(TokenObtainPairView):
    serializer_class = LoginSerializer


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def me(request):
    """Session restore — 1 indexed PK lookup, no password/token refresh needed."""
    return Response(UserBriefSerializer(request.user).data)
