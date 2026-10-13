from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ("name", "email", "role", "is_active")
    list_filter = ("role", "is_active")
    search_fields = ("name", "email")
    ordering = ("-date_joined",)
    fieldsets = BaseUserAdmin.fieldsets + (
        ("Bhoj Bilash", {"fields": ("name", "role")}),
    )
    add_fieldsets = (
        (None, {"fields": ("email", "name", "role", "password1", "password2")}),
    )
