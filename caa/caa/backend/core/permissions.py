from rest_framework.permissions import SAFE_METHODS, BasePermission


class ReadAllEditorsWrite(BasePermission):
    """Any logged-in user can read; only faculty/admin can change official data."""
    def has_permission(self, request, view):
        u = request.user
        if not (u and u.is_authenticated):
            return False
        return request.method in SAFE_METHODS or u.is_editor


class IsModerator(BasePermission):
    def has_permission(self, request, view):
        u = request.user
        return bool(u and u.is_authenticated and u.is_moderator)
