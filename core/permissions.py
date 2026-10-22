from rest_framework.permissions import BasePermission


class AdminOnly(BasePermission):
    def has_permission(self, request, view):
        return bool(
            request.user.is_authenticated and request.user.is_active and request.user.is_staff
        )


class SuperAdminOnly(AdminOnly):
    def has_permission(self, request, view):
        return super().has_permission(request, view) and request.user.is_superuser
