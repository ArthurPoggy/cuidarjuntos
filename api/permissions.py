from rest_framework.permissions import BasePermission

from care.models import GroupMembership


class HasGroupMembership(BasePermission):
    """User must belong to a CareGroup."""

    message = "Voce precisa estar em um grupo de cuidado."

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        return GroupMembership.objects.filter(user=request.user).exists()


class IsSuperUser(BasePermission):
    """Only superusers."""

    def has_permission(self, request, view):
        return request.user and request.user.is_superuser


class IsRecordOwnerOrSuperuser(BasePermission):
    """Object-level: owner of the record or superuser."""

    def has_object_permission(self, request, view, obj):
        if request.user.is_superuser:
            return True
        return getattr(obj, "created_by_id", None) == request.user.id
