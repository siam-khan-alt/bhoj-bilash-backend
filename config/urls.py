from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/auth/", include("users.urls")),
    path("api/", include("menu.urls")),
    path("api/", include("orders.urls")),
    path("api/", include("khata.urls")),
    path("api/", include("settingsplus.urls")),
]
